type IconName =
  | "overview"
  | "document"
  | "plus"
  | "graph"
  | "shield"
  | "upload"
  | "check"
  | "alert"
  | "arrow"
  | "download"
  | "refresh"
  | "search"
  | "chevron"
  | "clock"
  | "building"
  | "scale"
  | "spark"
  | "external";

interface IconProps {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}

export function Icon({ name, size = 18, strokeWidth = 1.7 }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (name) {
    case "overview":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "document":
      return (
        <svg {...common}>
          <path d="M14 3H6.8A1.8 1.8 0 0 0 5 4.8v14.4A1.8 1.8 0 0 0 6.8 21h10.4a1.8 1.8 0 0 0 1.8-1.8V8z" />
          <path d="M14 3v5h5M8.5 12.5h7M8.5 16.5h5" />
        </svg>
      );
    case "plus":
      return (
        <svg {...common}>
          <path d="M12 5v14M5 12h14" />
        </svg>
      );
    case "graph":
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="2.4" />
          <circle cx="18" cy="7" r="2.4" />
          <circle cx="12" cy="18" r="2.4" />
          <path d="m8.2 7.1 7.6.1M7.1 8.1l3.7 7.7M16.8 9.3l-3.5 6.4" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3 5 6v5.5c0 4.2 2.9 7.5 7 9.5 4.1-2 7-5.3 7-9.5V6z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "upload":
      return (
        <svg {...common}>
          <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
          <path d="M4.5 15.5v2.7A1.8 1.8 0 0 0 6.3 20h11.4a1.8 1.8 0 0 0 1.8-1.8v-2.7" />
        </svg>
      );
    case "check":
      return (
        <svg {...common}>
          <path d="m5 12.5 4.2 4.2L19 6.8" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M12 3.8 21 20H3z" />
          <path d="M12 9v4.5M12 17h.01" />
        </svg>
      );
    case "arrow":
      return (
        <svg {...common}>
          <path d="M5 12h14m-5-5 5 5-5 5" />
        </svg>
      );
    case "download":
      return (
        <svg {...common}>
          <path d="M12 4v12m0 0 4.5-4.5M12 16l-4.5-4.5" />
          <path d="M4.5 18.5v1.2h15v-1.2" />
        </svg>
      );
    case "refresh":
      return (
        <svg {...common}>
          <path d="M20 7v5h-5M4 17v-5h5" />
          <path d="M18.1 9.5A7 7 0 0 0 6.2 6.2L4 8.5M5.9 14.5a7 7 0 0 0 11.9 3.3L20 15.5" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="10.5" cy="10.5" r="6.2" />
          <path d="m15.2 15.2 4.3 4.3" />
        </svg>
      );
    case "chevron":
      return (
        <svg {...common}>
          <path d="m8 10 4 4 4-4" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5V12l3 2" />
        </svg>
      );
    case "building":
      return (
        <svg {...common}>
          <path d="M4 20V5.5L12 3v17M12 20h8V9l-8-3" />
          <path d="M7 8h2M7 11.5h2M7 15h2M15 11h2M15 14.5h2M15 18h2M2 20h20" />
        </svg>
      );
    case "scale":
      return (
        <svg {...common}>
          <path d="M12 4v16M6 20h12M5 7h14M7 7l-3 6h6zM17 7l-3 6h6z" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
        </svg>
      );
    case "external":
      return (
        <svg {...common}>
          <path d="M14 4h6v6M20 4l-8 8" />
          <path d="M19 14v4.2A1.8 1.8 0 0 1 17.2 20H5.8A1.8 1.8 0 0 1 4 18.2V6.8A1.8 1.8 0 0 1 5.8 5H10" />
        </svg>
      );
  }
}
