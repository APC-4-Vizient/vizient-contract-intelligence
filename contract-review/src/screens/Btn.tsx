import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'cta' | 'outline' | 'tint';

interface BtnProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
  variant?: Variant;
  small?: boolean;
  icon?: ReactNode;
}

/** A Vizient pill button. See vizient-theme.css for the variants. */
export function Btn({ variant = 'primary', small = false, icon, type = 'button', children, ...rest }: BtnProps) {
  const classes = ['vz-btn'];
  if (variant !== 'primary') classes.push(`vz-btn--${variant}`);
  if (small) classes.push('vz-btn--sm');
  return (
    <button type={type} className={classes.join(' ')} {...rest}>
      {icon}
      {children}
    </button>
  );
}
