interface KPICardProps {
  title: string;
  value: string | number;
  suffix?: string;
  icon?: string;
}

export default function KPICard({ title, value, suffix = '', icon }: KPICardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">{title}</p>
          <p className="text-2xl font-bold mt-1">
            {value} <span className="text-lg text-gray-400">{suffix}</span>
          </p>
        </div>
        {icon && <span className="text-3xl">{icon}</span>}
      </div>
    </div>
  );
}
