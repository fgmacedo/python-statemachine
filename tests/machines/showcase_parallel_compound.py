from statemachine import State
from statemachine import StateChart


class ParallelCompoundSC(StateChart):
    """Parallel regions with a cross-boundary transition into an inner compound.

    The ``rebuild`` transition targets ``pipeline.build`` — a compound state
    inside a parallel region.  This is the exact pattern that triggers
    `mermaid-js/mermaid#4052 <https://github.com/mermaid-js/mermaid/issues/4052>`_;
    the Mermaid renderer works around it by redirecting the arrow to the
    compound's initial child.

    {statechart:rst}
    """

    class pipeline(State.Parallel, name="Pipeline"):
        class build(State.Compound, name="Build"):
            compile = State(initial=True)
            link = State(final=True)
            do_build = compile.to(link)

        class test(State.Compound, name="Test"):
            unit = State(initial=True)
            e2e = State(final=True)
            do_test = unit.to(e2e)

    idle = State(initial=True)
    review = State()

    start = idle.to(pipeline)
    done_state_pipeline = pipeline.to(review)
    rebuild = review.to(pipeline.build)
    accept = review.to(idle)
