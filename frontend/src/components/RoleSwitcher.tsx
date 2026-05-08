import { UserRole } from "@/lib/api";

const ROLES: Array<{
  label: string;
  value: UserRole;
}> = [
  { label: "Student", value: "student" },
  { label: "Faculty", value: "faculty" },
  { label: "Admin", value: "admin" },
];

type RoleSwitcherProps = {
  value: UserRole;
  onChange: (role: UserRole) => void;
};

export function RoleSwitcher({ value, onChange }: RoleSwitcherProps) {
  return (
    <div className="flex rounded-lg border border-zinc-200 bg-zinc-100 p-1">
      {ROLES.map((role) => {
        const isSelected = role.value === value;
        return (
          <button
            className={`rounded-md px-3 py-2 text-sm font-medium transition ${
              isSelected
                ? "bg-white text-teal-800 shadow-sm"
                : "text-zinc-600 hover:bg-white/70 hover:text-zinc-950"
            }`}
            key={role.value}
            onClick={() => onChange(role.value)}
            type="button"
          >
            {role.label}
          </button>
        );
      })}
    </div>
  );
}
