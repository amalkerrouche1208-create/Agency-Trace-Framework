### Orphan Reopen Events

A `suggestion-reopen` is associated with the most recently observable
suggestion episode when such an antecedent exists.

If a reopen event occurs without any observable prior suggestion episode
within the session, AgencyTrace does not create or infer an artificial
episode. The event is retained as an **orphan reopen** and reported by the
reconstruction audit.

This preserves the raw trace while avoiding speculative attribution.