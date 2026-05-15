"""
SQLite-backed approval workflow
================================

Real-world state machines often need to survive process restarts. This example
shows how to **persist a StateChart configuration to a relational database**,
using the same property getter/setter pattern that ORMs like Django and
SQLAlchemy use under the hood.

We build a **document approval workflow** where each document must pass both a
legal and a technical review (parallel tracks) before it can be approved. If
**any** reviewer rejects, the document is rejected immediately — the entire
parallel state is exited at once.

The example also compares two configuration update strategies controlled by
:attr:`~statemachine.statemachine.StateChart.atomic_configuration_update`:

- **Incremental** (``False``, ``StateChart`` default, SCXML-spec compliant):
  the configuration is updated state-by-state as the engine enters and exits
  states during a microstep.
- **Atomic** (``True``, ``StateMachine`` default): the full configuration is
  computed first and written in a single operation — fewer database writes
  per transition.

"""

import sqlite3

from statemachine.orderedset import OrderedSet

from statemachine import State
from statemachine import StateChart

# %%
# Database abstraction
# --------------------
#
# ``WorkflowDB`` manages two tables:
#
# - **documents** — each row is a domain entity with ``id``, ``title``,
#   ``author``, and a ``state`` column that holds the serialized state chart
#   configuration.
# - **state_history** — an append-only log of every state mutation, useful for
#   auditing, debugging, or building a timeline view.
#
# The state is serialized as a comma-separated string. ``NULL`` means
# "no state yet" (the state chart will enter its initial state on creation).


class WorkflowDB:
    """SQLite persistence layer for document workflows."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE documents ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  author TEXT NOT NULL,"
            "  state TEXT"
            ")"
        )
        self.conn.execute(
            "CREATE TABLE state_history ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  document_id INTEGER NOT NULL REFERENCES documents(id),"
            "  old_state TEXT,"
            "  new_state TEXT"
            ")"
        )
        self.conn.commit()

    def insert_document(self, title, author):
        """Insert a new document and return its id."""
        cur = self.conn.execute(
            "INSERT INTO documents (title, author) VALUES (?, ?)", (title, author)
        )
        self.conn.commit()
        return cur.lastrowid

    def find_document(self, doc_id):
        """Return ``(title, author)`` for the given document."""
        return self.conn.execute(
            "SELECT title, author FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

    def get_state(self, doc_id):
        """Read state from the DB and deserialize."""
        raw = self.conn.execute("SELECT state FROM documents WHERE id = ?", (doc_id,)).fetchone()[
            0
        ]
        if raw is None:
            return None
        parts = raw.split(",")
        return parts[0] if len(parts) == 1 else OrderedSet(parts)

    def set_state(self, doc_id, value):
        """Serialize state, persist it, and record the mutation in history."""
        old_raw = self.conn.execute(
            "SELECT state FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()[0]

        if value is None:
            new_raw = None
        elif isinstance(value, OrderedSet):
            new_raw = ",".join(str(v) for v in value)
        else:
            new_raw = str(value)

        self.conn.execute("UPDATE documents SET state = ? WHERE id = ?", (new_raw, doc_id))
        self.conn.execute(
            "INSERT INTO state_history (document_id, old_state, new_state) VALUES (?, ?, ?)",
            (doc_id, old_raw, new_raw),
        )
        self.conn.commit()

    def all_documents(self):
        """Return all rows from the documents table."""
        return self.conn.execute(
            "SELECT id, title, author, state FROM documents ORDER BY id"
        ).fetchall()

    def history_for(self, doc_id):
        """Return the state mutation history for a specific document."""
        return self.conn.execute(
            "SELECT id, old_state, new_state FROM state_history WHERE document_id = ? ORDER BY id",
            (doc_id,),
        ).fetchall()

    def mutation_count(self):
        """Return the total number of state mutations recorded."""
        return self.conn.execute("SELECT COUNT(*) FROM state_history").fetchone()[0]

    def close(self):
        self.conn.close()


# %%
# Domain model
# ------------
#
# ``Document`` is a domain entity. Its ``state`` property reads from and writes
# to the database **on every access** — each getter call returns a **freshly
# deserialized** object. This is exactly how Django model fields and
# SQLAlchemy column properties work: the ORM never hands you the same Python
# object twice.
#
# Each ``Document`` owns a workflow instance, following the same pattern as
# :class:`~statemachine.mixins.MachineMixin`: the model holds a reference to
# its state machine. The workflow class is injected at creation time, keeping
# the model decoupled from any specific chart definition.


class Document:
    """A document that needs approval."""

    def __init__(self, store, doc_id, title, author):
        self.store = store
        self.id = doc_id
        self.title = title
        self.author = author
        self.workflow: "ApprovalWorkflow | None" = None

    @classmethod
    def create(cls, store, workflow_cls, title, author):
        """Insert a new document into the DB and start its workflow."""
        doc_id = store.insert_document(title, author)
        doc = cls(store, doc_id, title, author)
        doc.workflow = workflow_cls(model=doc)
        return doc

    @classmethod
    def load(cls, store, workflow_cls, doc_id):
        """Restore a document and its workflow from the DB."""
        title, author = store.find_document(doc_id)
        doc = cls(store, doc_id, title, author)
        doc.workflow = workflow_cls(model=doc)
        return doc

    @property
    def state(self):
        return self.store.get_state(self.id)

    @state.setter
    def state(self, value):
        self.store.set_state(self.id, value)

    def __repr__(self):
        config = list(self.workflow.configuration_values) if self.workflow else "?"
        return f"Document(#{self.id} {self.title!r} by {self.author}, state={config})"


# %%
# Approval workflow
# -----------------
#
# A document starts as a **draft**. When submitted, it enters a **parallel**
# review state: legal and technical tracks run independently.
#
# - **Both approve** → ``done.state.review`` fires → **approved**
# - **Any reviewer rejects** → exits the entire parallel state → **rejected**


class ApprovalWorkflow(StateChart):
    """Document approval with parallel legal and technical review tracks."""

    draft = State("Draft", initial=True)

    class review(State.Parallel):
        class legal_track(State.Compound):
            legal_pending = State("Legal Pending", initial=True)
            legal_approved = State("Legal Approved", final=True)

            approve_legal = legal_pending.to(legal_approved)

        class tech_track(State.Compound):
            tech_pending = State("Tech Pending", initial=True)
            tech_approved = State("Tech Approved", final=True)

            approve_tech = tech_pending.to(tech_approved)

    submit = draft.to(review)

    approved = State("Approved", final=True)
    rejected = State("Rejected", final=True)

    done_state_review = review.to(approved)
    reject_legal = review.to(rejected)
    reject_tech = review.to(rejected)


# %%
# Here is the workflow diagram — note the two parallel regions inside
# ``review`` and the ``reject_legal`` / ``reject_tech`` transitions that exit
# the entire parallel state at once.

sm = ApprovalWorkflow()

# %%

sm


# %%
# Display helper
# ~~~~~~~~~~~~~~


def print_table(headers, rows):
    """Print a simple formatted table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val) if val is not None else "NULL"))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*(str(v) if v is not None else "NULL" for v in row)))


# %%
# Incremental configuration updates
# ----------------------------------
#
# ``StateChart`` defaults to ``atomic_configuration_update=False``, following
# the SCXML specification: the configuration is modified state-by-state as the
# engine enters and exits states during each microstep (``configuration.add()``
# and ``configuration.discard()`` in the W3C algorithm).
#
# Each ``add()`` or ``discard()`` call triggers the model's ``state`` property
# setter, which writes to the database. This means you'll see **one DB write
# per state** entered or exited — fine for correctness, but chatty for
# persistence layers.

db_inc = WorkflowDB()

alice = Document.create(db_inc, ApprovalWorkflow, "RFC-001: API Redesign", "Alice")
bob = Document.create(db_inc, ApprovalWorkflow, "RFC-002: DB Migration", "Bob")

print(f"Created: {alice}")
print(f"Created: {bob}")

assert alice.state == "draft"
assert bob.state == "draft"

# %%
# Alice's document goes through full approval.

alice.workflow.send("submit")
print(f"After submit:   {alice}")

alice.workflow.send("approve_legal")
print(f"Legal approved: {alice}")
assert "legal_approved" in alice.workflow.configuration_values
assert "tech_pending" in alice.workflow.configuration_values

alice.workflow.send("approve_tech")
print(f"Fully approved: {alice}")

# %%
# When both tracks reach their final state, ``done.state.review`` fires
# automatically and the workflow transitions to **approved**.

assert alice.workflow.approved.is_active
assert alice.state == "approved"

# %%
# Bob's document is **rejected** by the legal team. The ``reject_legal``
# event transitions out of the ``review`` parallel state, exiting all child
# states at once — even though technical review hasn't started yet.

bob.workflow.send("submit")
bob.workflow.send("reject_legal")
print(f"Rejected:       {bob}")
assert bob.workflow.rejected.is_active
assert bob.state == "rejected"

# %%
# Documents table (incremental mode)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

print()
print_table(["id", "title", "author", "state"], db_inc.all_documents())

# %%
# State mutation history — Alice's document
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# Every ``add()`` / ``discard()`` call during state entry or exit is a
# separate DB write. The history reveals the step-by-step construction and
# teardown of the parallel configuration:
#
# ``draft`` → ``NULL`` → ``review`` → add ``legal_track`` → add
# ``legal_pending`` → add ``tech_track`` → add ``tech_pending`` → ...

print()
print_table(["#", "old_state", "new_state"], db_inc.history_for(alice.id))

inc_mutations = db_inc.mutation_count()
print(f"\nTotal mutations (incremental, 2 docs): {inc_mutations}")


# %%
# Atomic configuration updates
# -----------------------------
#
# Setting ``atomic_configuration_update=True`` changes the strategy: the
# engine computes the full new configuration first, then writes it in a
# **single** ``setattr`` call. This means one DB write per microstep instead
# of one per state — a significant reduction for parallel charts.
#
# We can enable this with a one-line subclass:


class ApprovalWorkflowAtomic(ApprovalWorkflow):
    """Same workflow with atomic configuration updates."""

    atomic_configuration_update = True


# %%
# Run the same scenario with atomic updates.

db_atom = WorkflowDB()

alice2 = Document.create(db_atom, ApprovalWorkflowAtomic, "RFC-001: API Redesign", "Alice")
bob2 = Document.create(db_atom, ApprovalWorkflowAtomic, "RFC-002: DB Migration", "Bob")

alice2.workflow.send("submit")
alice2.workflow.send("approve_legal")
alice2.workflow.send("approve_tech")
assert alice2.state == "approved"

bob2.workflow.send("submit")
bob2.workflow.send("reject_legal")
assert bob2.state == "rejected"

print(f"Alice: {alice2}")
print(f"Bob:   {bob2}")

# %%
# State mutation history — Alice's document (atomic mode)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# Each microstep now produces **one** DB write with the full configuration.
# No intermediate states are visible.

print()
print_table(["#", "old_state", "new_state"], db_atom.history_for(alice2.id))

atom_mutations = db_atom.mutation_count()
print(f"\nTotal mutations (atomic, 2 docs): {atom_mutations}")

# %%
# Comparison
# ~~~~~~~~~~
#
# Both modes produce identical final states, but atomic mode generates
# significantly fewer database writes — especially with parallel states where
# many children are entered and exited simultaneously.

print(f"\nIncremental: {inc_mutations} mutations")
print(f"Atomic:      {atom_mutations} mutations")
assert atom_mutations < inc_mutations


# %%
# State restoration from the database
# ------------------------------------
#
# The real test of persistence: delete the Python objects and recreate them
# from the database. The state chart should resume exactly where it left off,
# preserving even parallel configurations.

alice_id = alice.id
alice_config = list(alice.workflow.configuration_values)
del alice

alice_restored = Document.load(db_inc, ApprovalWorkflow, alice_id)
print(f"Restored: {alice_restored}")
assert list(alice_restored.workflow.configuration_values) == alice_config

# %%
# Bob's rejection is also preserved — no state is lost.

bob_id = bob.id
del bob

bob_restored = Document.load(db_inc, ApprovalWorkflow, bob_id)
print(f"Restored: {bob_restored}")
assert bob_restored.state == "rejected"

# %%
# Final documents table
# ~~~~~~~~~~~~~~~~~~~~~~

print()
print_table(["id", "title", "author", "state"], db_inc.all_documents())


# %%
# Cleanup.

db_inc.close()
db_atom.close()
