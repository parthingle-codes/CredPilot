import { useRef, type KeyboardEvent } from 'react'

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  onRun?: () => void
  placeholder?: string
  ariaLabel: string
}

export function CodeEditor({
  value,
  onChange,
  onRun,
  placeholder,
  ariaLabel,
}: CodeEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const gutterRef = useRef<HTMLDivElement>(null)
  const lineCount = Math.max(1, value.split('\n').length)
  const lineNumbers = Array.from({ length: lineCount }, (_, index) => index + 1)

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Tab') {
      event.preventDefault()
      const element = event.currentTarget
      element.setRangeText('  ', element.selectionStart, element.selectionEnd, 'end')
      onChange(element.value)
      return
    }

    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      onRun?.()
    }
  }

  return (
    <div className="editor-shell">
      <div className="editor-gutter" ref={gutterRef} aria-hidden="true">
        {lineNumbers.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </div>
      <textarea
        ref={textareaRef}
        className="code-textarea"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        onScroll={(event) => {
          if (gutterRef.current) {
            gutterRef.current.scrollTop = event.currentTarget.scrollTop
          }
        }}
        placeholder={placeholder}
        aria-label={ariaLabel}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        wrap="off"
      />
    </div>
  )
}
