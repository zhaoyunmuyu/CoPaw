export function shouldEnqueueFollowUpSubmission(
  loading: boolean,
  sessionGenerating: boolean,
) {
  return loading || sessionGenerating;
}
