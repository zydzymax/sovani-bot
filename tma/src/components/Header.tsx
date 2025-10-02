interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
      {subtitle && <p className="text-gray-600 dark:text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}
