import { TestBed } from '@angular/core/testing'
import { EventManager } from '@angular/platform-browser'
import { DOCUMENT } from '@angular/common'

import { HotKeyService } from './hot-key.service'

describe('HotKeyService', () => {
  let service: HotKeyService
  let eventManager: EventManager
  let document: Document

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [HotKeyService, EventManager],
    })
    service = TestBed.inject(HotKeyService)
    eventManager = TestBed.inject(EventManager)
    document = TestBed.inject(DOCUMENT)
  })

  it('should support adding a shortcut', () => {
    const callback = jest.fn()
    const addEventListenerSpy = jest.spyOn(eventManager, 'addEventListener')

    const observable = service
      .addShortcut({ keys: 'control.a' })
      .subscribe(() => {
        callback()
      })

    expect(addEventListenerSpy).toHaveBeenCalled()

    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'a', ctrlKey: true })
    )
    expect(callback).toHaveBeenCalled()

    //coverage
    observable.unsubscribe()
  })
})
