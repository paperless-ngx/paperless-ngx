import { TestBed } from '@angular/core/testing'
import { Toast, ToastLevel, ToastService } from './toast.service'

describe('ToastService', () => {
  let toastService: ToastService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ToastService],
    })

    toastService = TestBed.inject(ToastService)
  })

  it('adds toast on show', () => {
    const toast = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    toastService.show(toast)

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts).toContainEqual(toast)
    })
  })

  it('adds a unique id to toast on show', () => {
    const toast = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    toastService.show(toast)

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts[0].id).toBeDefined()
    })
  })

  it('parses error string to object on show', () => {
    const toast = {
      title: 'Title',
      content: 'content',
      delay: 5000,
      error: 'Error string',
    }
    toastService.show(toast)

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts[0].error).toEqual('Error string')
    })
  })

  it('creates toasts with defaults on showInfo and showError', () => {
    toastService.showInfo('Info toast')
    toastService.showError('Error toast')

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts).toContainEqual({
        content: 'Info toast',
        delay: 5000,
      })
      expect(toasts).toContainEqual({
        content: 'Error toast',
        delay: 10000,
      })
    })
  })

  it('keeps showInfo toasts out of the toast list', () => {
    let toasts: Toast[] = []
    const popups: Toast[] = []
    toastService.getToasts().subscribe((t) => (toasts = [...t]))
    toastService.showToast.subscribe((t) => popups.push(t))

    toastService.showInfo('Info toast')
    toastService.showError('Error toast')

    expect(popups.map((t) => t.content)).toEqual(['Info toast', 'Error toast'])
    expect(toasts.map((t) => t.content)).toEqual(['Error toast'])
  })

  it('adds toasts to the list unless persistent is false', () => {
    let toasts: Toast[] = []
    toastService.getToasts().subscribe((t) => (toasts = [...t]))

    toastService.show({ content: 'kept', delay: 5000 })
    toastService.show({ content: 'kept too', delay: 5000, persistent: true })
    toastService.show({ content: 'popup only', delay: 5000, persistent: false })

    expect(toasts.map((t) => t.content)).toEqual(['kept too', 'kept'])
  })

  it('still pops up non-persistent toasts while popups are suppressed', () => {
    const popups: Toast[] = []
    toastService.suppressPopupToasts = true
    toastService.showToast.subscribe((t) => popups.push(t))

    toastService.show({ content: 'kept', delay: 5000 })
    toastService.showInfo('popup only')

    expect(popups.map((t) => t?.content)).toEqual(['popup only'])
  })

  it('removes toast on close', () => {
    const toast = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    toastService.show(toast)
    toastService.closeToast(toast)

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts).toHaveLength(0)
    })
  })

  it('clears all toasts on clearToasts', () => {
    toastService.showInfo('Info toast')
    toastService.showError('Error toast')
    toastService.clearToasts()

    toastService.getToasts().subscribe((toasts) => {
      expect(toasts).toHaveLength(0)
    })
  })

  it('suppresses popup toasts if suppressPopupToasts is true', (finish) => {
    toastService.showToast.subscribe((toast) => {
      expect(toast).not.toBeNull()
    })
    toastService.showInfo('Info toast')

    toastService.showToast.subscribe((toast) => {
      expect(toast).toBeNull()
      finish()
    })

    toastService.suppressPopupToasts = true
    toastService.showInfo('Info toast')
  })

  it('sets the level for showSuccess, showInfo and showError', () => {
    const shown: Toast[] = []
    toastService.showToast.subscribe((t) => shown.push(t))
    toastService.showSuccess('Saved')
    toastService.showInfo('Started')
    toastService.showError('Failed')
    expect(shown.map((t) => t.level)).toEqual([
      ToastLevel.Success,
      undefined,
      ToastLevel.Error,
    ])
  })
})
