import Picker, { EmojiStyle, SuggestionMode, Theme } from 'emoji-picker-react'

/**
 * Full Unicode emoji picker (search, categories, skin tones, recently used).
 * Native style = the device's own emoji font: no images are downloaded from a CDN.
 * Loaded lazily by EmojiButton so it is not part of the initial bundle.
 */
export default function EmojiPanel({ onSelect }: { onSelect: (emoji: string) => void }) {
  return (
    <Picker
      onEmojiClick={(data) => onSelect(data.emoji)}
      emojiStyle={EmojiStyle.NATIVE}
      theme={Theme.LIGHT}
      suggestedEmojisMode={SuggestionMode.RECENT}
      autoFocusSearch={false}
      lazyLoadEmojis
      previewConfig={{ showPreview: false }}
      searchPlaceholder="Search emoji"
      width="100%"
      height={380}
    />
  )
}
