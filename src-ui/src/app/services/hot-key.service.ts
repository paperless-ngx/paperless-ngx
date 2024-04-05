import { DOCUMENT } from '@angular/common'
import { Inject, Injectable } from '@angular/core'
import { EventManager } from '@angular/platform-browser'
import { Observable } from 'rxjs'

export interface ShortcutOptions {
  element?: any
  keys: string
}

@Injectable({
  providedIn: 'root',
})
export class HotKeyService {
  defaults: Partial<ShortcutOptions> = {
    element: this.document,
  }

  constructor(
    private eventManager: EventManager,
    @Inject(DOCUMENT) private document: Document
  ) {}

  addShortcut(options: ShortcutOptions) {
    const merged = { ...this.defaults, ...options }
    const event = `keydown.${merged.keys}`

    return new Observable((observer) => {
      const handler = (e) => {
        e.preventDefault()
        observer.next(e)
      }

      const dispose = this.eventManager.addEventListener(
        merged.element,
        event,
        handler
      )

      return () => {
        dispose()
      }
    })
  }
}
