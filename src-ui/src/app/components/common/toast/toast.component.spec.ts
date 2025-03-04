import {
  ComponentFixture,
  discardPeriodicTasks,
  fakeAsync,
  flush,
  TestBed,
  tick,
} from '@angular/core/testing'

import { Clipboard } from '@angular/cdk/clipboard'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
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

  it('should countdown toast', fakeAsync(() => {
    component.toast = toast2
    fixture.detectChanges()
    component.onShown(toast2)
    tick(5000)
    expect(component.toast.delayRemaining).toEqual(0)
    flush()
    discardPeriodicTasks()
  }))

  it('should show an error if given with toast', fakeAsync(() => {
    component.toast = toast1
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain('Error 1 content')

    flush()
    discardPeriodicTasks()
  }))

  it('should show error details, support copy', fakeAsync(() => {
    component.toast = toast2
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain(
      'Error 2 message details'
    )

    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyError(toast2.error)
    expect(copySpy).toHaveBeenCalled()

    flush()
    discardPeriodicTasks()
  }))

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
