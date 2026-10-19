import { ComponentFixture, TestBed } from '@angular/core/testing'

import { Clipboard } from '@angular/cdk/clipboard'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ToastLevel } from 'src/app/services/toast.service'
import { ToastComponent } from './toast.component'

const toast1 = {
  content: 'Error 1 content',
  delay: 5000,
  error: 'Error 1 string',
}

const toast2 = {
  content: 'Error 2 content',
  delay: 5000,
  error: {
    url: 'https://example.com',
    status: 500,
    statusText: 'Internal Server Error',
    message: 'Internal server error 500 message',
    error: { detail: 'Error 2 message details' },
  },
}

describe('ToastComponent', () => {
  let component: ToastComponent
  let fixture: ComponentFixture<ToastComponent>
  let clipboard: Clipboard

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ToastComponent, NgxBootstrapIconsModule.pick(allIcons)],
    }).compileComponents()

    fixture = TestBed.createComponent(ToastComponent)
    clipboard = TestBed.inject(Clipboard)
    component = fixture.componentInstance
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should countdown toast', () => {
    jest.useFakeTimers()
    component.toast = toast2
    fixture.detectChanges()
    component.onShown(toast2)
    jest.advanceTimersByTime(5000 + 150) // ticks every 150ms
    expect(component.delayRemaining()).toEqual(0)
    jest.useRealTimers()
  })

  it('should start the progress bar full before the countdown begins', () => {
    component.toast = { content: 'Info', delay: 3000 }
    fixture.detectChanges()
    expect(component.delayRemaining()).toEqual(3000)
  })

  it('should hide the toast when the countdown ends', () => {
    jest.useFakeTimers()
    const toast = { content: 'Info', delay: 3000 }
    component.toast = toast
    fixture.detectChanges()
    const hideSpy = jest.spyOn(component.ngbToast, 'hide')
    component.onShown(toast)
    jest.advanceTimersByTime(2850)
    expect(hideSpy).not.toHaveBeenCalled()
    jest.advanceTimersByTime(300)
    expect(hideSpy).toHaveBeenCalled()
    jest.useRealTimers()
  })

  it('should pause the countdown while hovered', () => {
    jest.useFakeTimers()
    const toast = { content: 'Info', delay: 3000 }
    component.toast = toast
    fixture.detectChanges()
    const hideSpy = jest.spyOn(component.ngbToast, 'hide')
    const el: HTMLElement = fixture.nativeElement.querySelector('ngb-toast')
    component.onShown(toast)
    jest.advanceTimersByTime(1500)
    el.dispatchEvent(new MouseEvent('mouseenter'))
    const remaining = component.delayRemaining()
    jest.advanceTimersByTime(10000)
    expect(component.delayRemaining()).toEqual(remaining)
    expect(hideSpy).not.toHaveBeenCalled()

    el.dispatchEvent(new MouseEvent('mouseleave'))
    jest.advanceTimersByTime(remaining + 150)
    expect(hideSpy).toHaveBeenCalled()
    jest.useRealTimers()
  })

  it('should pause the countdown while focus is inside', () => {
    jest.useFakeTimers()
    const toast = { content: 'Info', delay: 3000 }
    component.toast = toast
    fixture.detectChanges()
    const el: HTMLElement = fixture.nativeElement.querySelector('ngb-toast')
    component.onShown(toast)
    el.dispatchEvent(new FocusEvent('focusin'))
    // mouse leaving doesn't resume while focus is still inside
    el.dispatchEvent(new MouseEvent('mouseenter'))
    el.dispatchEvent(new MouseEvent('mouseleave'))
    jest.advanceTimersByTime(5000)
    expect(component.delayRemaining()).toEqual(3000)
    el.dispatchEvent(new FocusEvent('focusout'))
    jest.advanceTimersByTime(3000)
    expect(component.delayRemaining()).toEqual(0)
    jest.useRealTimers()
  })

  it('should not count down without autohide', () => {
    jest.useFakeTimers()
    const toast = { content: 'Info', delay: 3000 }
    component.toast = toast
    component.autohide = false
    fixture.detectChanges()
    component.onShown(toast)
    jest.advanceTimersByTime(5000)
    expect(component.delayRemaining()).toBeNull()
    jest.useRealTimers()
  })

  it('should show an icon and colors for each level', () => {
    component.toast = {
      content: 'Saved',
      delay: 5000,
      level: ToastLevel.Success,
    }
    fixture.detectChanges()
    const el: HTMLElement = fixture.nativeElement
    expect(el.querySelector('i-bs[name="check-circle"]')).not.toBeNull()
    expect(el.querySelector('ngb-toast').classList).not.toContain('toast-error')

    fixture = TestBed.createComponent(ToastComponent)
    fixture.componentInstance.toast = {
      content: 'Failed',
      delay: 5000,
      level: ToastLevel.Error,
    }
    fixture.detectChanges()
    const errorEl: HTMLElement = fixture.nativeElement
    expect(
      errorEl.querySelector('i-bs[name="exclamation-triangle"]')
    ).not.toBeNull()
    expect(errorEl.querySelector('ngb-toast').classList).toContain(
      'toast-error'
    )

    fixture = TestBed.createComponent(ToastComponent)
    fixture.componentInstance.toast = { content: 'Started', delay: 5000 }
    fixture.detectChanges()
    expect(
      fixture.nativeElement.querySelector('i-bs[name="info-circle"]')
    ).not.toBeNull()
  })

  it('should show an error if given with toast', () => {
    component.toast = toast1
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain('Error 1 content')
  })

  it('should show error details, support copy', () => {
    component.toast = toast2
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain(
      'Error 2 message details'
    )

    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyError(toast2.error)
    expect(copySpy).toHaveBeenCalled()
  })

  it('should parse error text, add ellipsis', () => {
    expect(component.getErrorText(toast2.error)).toEqual(
      'Error 2 message details'
    )
    expect(component.getErrorText({ error: 'Error string no detail' })).toEqual(
      'Error string no detail'
    )
    expect(component.getErrorText('Error string')).toEqual('')
    expect(
      component.getErrorText({ error: { message: 'foo error bar' } })
    ).toContain('{"message":"foo error bar"}')
    expect(
      component.getErrorText({ error: new Array(205).join('a') })
    ).toContain('...')
  })
})
