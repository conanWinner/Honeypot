import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/utils'

const buttonStyles = cva(
  'inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variant: {
        seal: 'bg-seal text-white hover:bg-seal-deep',
        ink: 'bg-ink text-paper hover:bg-black',
        ghost: 'border border-line bg-card text-ink hover:bg-paper-deep',
        quiet: 'text-ink-soft hover:text-ink',
      },
      size: {
        md: 'h-10',
        sm: 'h-8 px-3 text-xs',
      },
    },
    defaultVariants: { variant: 'ink', size: 'md' },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonStyles> & { asChild?: boolean }

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonStyles({ variant, size }), className)} {...props} />
}

export function Banner({ tone, children }: { tone: 'warn' | 'danger' | 'ok'; children: ReactNode }) {
  const toneClass = {
    warn: 'border-gold/40 bg-[#f8e7c8] text-[#6d4708]',
    danger: 'border-danger/30 bg-[#f8d9d2] text-danger',
    ok: 'border-pine/30 bg-[#e5f2ea] text-pine',
  }[tone]
  return <div className={cn('rounded-2xl border px-4 py-3 text-sm leading-6', toneClass)}>{children}</div>
}
