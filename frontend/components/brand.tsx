import Link from "next/link";
export function Brand({
  preserveWorkspace = false,
}: {
  preserveWorkspace?: boolean;
}) {
  return (
    <Link
      href="/"
      target={preserveWorkspace ? "_blank" : undefined}
      rel={preserveWorkspace ? "noreferrer" : undefined}
      className="brand"
      aria-label={
        preserveWorkspace ? "Clutch home (opens in a new tab)" : "Clutch home"
      }
    >
      <span className="brand-mark" aria-hidden="true">
        c<span>↗</span>
      </span>
      clutch<span className="brand-period">.</span>
    </Link>
  );
}
