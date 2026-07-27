import { Link } from "react-router-dom";
import { buttonClasses } from "@/lib/buttonStyles";

/*
 * A link that looks like a button.
 *
 * Navigation must stay an anchor for middle-click, copy-link and screen-reader
 * semantics, so this is deliberately NOT a <button>. It shares its classes with
 * DynamicButton via buttonClasses() so the two are visually identical.
 *
 * Pass `to` for internal routes (renders a react-router Link) or `href` for
 * external ones (renders an <a> with the right rel attributes).
 */
export default function LinkButton({
  to,
  href,
  children,
  variant = "outline",
  size = "default",
  className = "",
  external = false,
  ...props
}) {
  const classes = buttonClasses({ variant, size, className });

  if (href) {
    return (
      <a
        href={href}
        className={classes}
        {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        {...props}
      >
        {children}
      </a>
    );
  }

  return (
    <Link to={to} className={classes} {...props}>
      {children}
    </Link>
  );
}
