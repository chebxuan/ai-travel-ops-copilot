import Link from "next/link";
export default function Button({ href, variant, className = "", children, ...props }) {
  const classes = `button ${variant ? `button--${variant}` : ""} ${className}`;
  return href ? <Link href={href} className={classes} {...props}>{children}</Link> : <button type="button" className={classes} {...props}>{children}</button>;
}
