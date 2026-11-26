const TOKEN_BODY = '\\[(?:ĐÃ CHE|SỐ_GIẢ|STK_GIẢ|NGÂN_HÀNG|LINK_GIẢ|VÍ_GIẢ|ID_GIẢ|APP_GIẢ|TÊN_GIẢ|MÃ|HÃNG_GIẢ)\\]'
const IS_TOKEN = new RegExp(`^${TOKEN_BODY}$`)

export function RichText({ text, onDark = false }: { text: string; onDark?: boolean }) {
  const parts = text.split(new RegExp(`(${TOKEN_BODY})`, 'g'))
  return (
    <>
      {parts.map((part, index) =>
        IS_TOKEN.test(part) ? (
          <span
            key={`${part}-${index}`}
            className={
              onDark
                ? 'mx-0.5 inline-flex rounded-full bg-white/20 px-1.5 py-0.5 text-[11px] font-semibold'
                : 'mx-0.5 inline-flex rounded-full bg-[#e7e2d8] px-1.5 py-0.5 text-[11px] font-semibold text-ink-soft'
            }
          >
            {part}
          </span>
        ) : (
          <span key={`${index}-t`}>{part}</span>
        ),
      )}
    </>
  )
}

