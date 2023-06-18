import { TestBed } from '@angular/core/testing'
import { ToastService } from './toast.service'

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
})
