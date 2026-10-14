export function CancelExecution({
  disabled,
  onCancel,
}: {
  disabled?: boolean;
  onCancel: () => void;
}) {
  return (
    <button
      type="button"
      data-testid="cancel-execution"
      disabled={disabled}
      onClick={onCancel}
    >
      Cancel execution
    </button>
  );
}
