
interface ActionRowProps {
  title: string;
  meta: string;
  onClick: () => void;
}

export function ActionRow({ title, meta, onClick }: ActionRowProps) {
  return (
    <div 
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        height: '64px',
        padding: '0 16px',
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
        borderBottom: '1px solid var(--surface-2)',
        transition: 'background-color var(--d-hover) var(--ease-out)'
      }}
      onMouseEnter={e => e.currentTarget.style.backgroundColor = 'var(--surface-2)'}
      onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <div style={{ width: '6px', height: '6px', backgroundColor: 'var(--text)', transform: 'rotate(45deg)' }}></div>
        <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text)' }}>
          {title}
        </div>
      </div>
      <div style={{
        fontSize: '12px',
        color: 'var(--text)',
        opacity: 0.6,
        marginLeft: '14px',
        marginTop: '4px'
      }}>
        {meta}
      </div>
    </div>
  );
}
