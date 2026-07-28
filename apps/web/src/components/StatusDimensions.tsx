type StatusDimensionsProps = {
  lifecycleStatus: string;
  evidenceStatus: string;
  approvalStatus: string;
};

export function StatusDimensions({
  lifecycleStatus,
  evidenceStatus,
  approvalStatus,
}: StatusDimensionsProps) {
  return (
    <dl className="status-dimensions">
      <div>
        <dt>Lifecycle</dt>
        <dd>{lifecycleStatus}</dd>
      </div>
      <div>
        <dt>Evidence</dt>
        <dd>{evidenceStatus}</dd>
      </div>
      <div>
        <dt>Approval</dt>
        <dd>{approvalStatus}</dd>
      </div>
    </dl>
  );
}
