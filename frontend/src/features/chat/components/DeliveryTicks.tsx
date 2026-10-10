import { Icon } from '../../../components/ui'
import type { ChatMessage } from '../../../types'

/** Clock while sending, alert when failed, then ✓ sent / ✓✓ delivered / blue ✓✓ read. */
export function DeliveryTicks({ message }: { message: ChatMessage }) {
  if (message.localState === 'sending') return <Icon.Clock className="h-3.5 w-3.5" aria-label="sending" aria-hidden={false} role="img" />
  if (message.localState === 'failed') return <Icon.Alert className="h-3.5 w-3.5 text-red-200" aria-label="not sent" aria-hidden={false} role="img" />
  if (message.status === 'read')
    return <Icon.DoubleCheck className="h-3.5 w-4 text-sky-300" aria-label="read" aria-hidden={false} role="img" />
  if (message.status === 'delivered')
    return <Icon.DoubleCheck className="h-3.5 w-4" aria-label="delivered" aria-hidden={false} role="img" />
  return <Icon.Check className="h-3.5 w-3.5" aria-label="sent" aria-hidden={false} role="img" />
}
