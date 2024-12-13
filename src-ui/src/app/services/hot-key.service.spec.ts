import { DOCUMENT } from '@angular/common'
import { TestBed } from '@angular/core/testing'
import { EventManager } from '@angular/platform-browser'

import { NgbModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap'
import { HotKeyService } from './hot-key.service'

describe('HotKeyService', () => {
  let service: HotKeyService
  let eventManager: EventManager
  let document: Document
  let modalService: NgbModal

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [HotKeyService, EventManager],
      imports: [NgbModalModule],
    })
    service = TestBed.inject(HotKeyService)
    eventManager = TestBed.inject(EventManager)
    document = TestBed.inject(DOCUMENT)
    modalService = TestBed.inject(NgbModal)
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

  it('should support adding a shortcut with a description, show modal', () => {
    const addEventListenerSpy = jest.spyOn(eventManager, 'addEventListener')
    service
      .addShortcut({ keys: 'control.a', description: 'Select all' })
      .subscribe()
    expect(addEventListenerSpy).toHaveBeenCalled()
    const modalSpy = jest.spyOn(modalService, 'open')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: '?', shiftKey: true })
    )
    expect(modalSpy).toHaveBeenCalled()
  })

  it('should ignore keydown events from input elements that dont have a modifier key', () => {
    // constructor adds a shortcut for shift.?
    const modalSpy = jest.spyOn(modalService, 'open')
    const input = document.createElement('input')
    const textArea = document.createElement('textarea')
    const event = new KeyboardEvent('keydown', { key: '?', shiftKey: true })
    jest.spyOn(event, 'target', 'get').mockReturnValue(input)
    document.dispatchEvent(event)
    jest.spyOn(event, 'target', 'get').mockReturnValue(textArea)
    document.dispatchEvent(event)
    expect(modalSpy).not.toHaveBeenCalled()
  })

  it('should dismiss all modals on escape and not fire event', () => {
    const callback = jest.fn()
    service
      .addShortcut({ keys: 'escape', description: 'Escape' })
      .subscribe(callback)
    const modalSpy = jest.spyOn(modalService, 'open')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: '?', shiftKey: true })
    )
    expect(modalSpy).toHaveBeenCalled()
    const dismissAllSpy = jest.spyOn(modalService, 'dismissAll')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(dismissAllSpy).toHaveBeenCalled()
    expect(callback).not.toHaveBeenCalled()
  })

  it('should not fire event on escape when open dropdowns ', () => {
    const callback = jest.fn()
    service
      .addShortcut({ keys: 'escape', description: 'Escape' })
      .subscribe(callback)
    const dropdown = document.createElement('div')
    dropdown.classList.add('dropdown-menu', 'show')
    document.body.appendChild(dropdown)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(callback).not.toHaveBeenCalled()
  })
})
