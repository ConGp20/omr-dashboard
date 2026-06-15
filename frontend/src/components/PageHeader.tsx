export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-5 mt-10 flex flex-wrap items-end justify-between gap-3 md:mt-0">
      <div>
        <h1 className="text-xl font-bold text-fg">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
