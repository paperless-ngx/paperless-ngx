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
import { NotificationComponent } from './notification.component'

const notification1 = {
  content: 'Error 1 content',
  delay: 5000,
  error: 'Error 1 string',
}

const notification2 = {
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

describe('NotificationComponent', () => {
  let component: NotificationComponent
  let fixture: ComponentFixture<NotificationComponent>
  let clipboard: Clipboard

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationComponent, NgxBootstrapIconsModule.pick(allIcons)],
    }).compileComponents()

    fixture = TestBed.createComponent(NotificationComponent)
    clipboard = TestBed.inject(Clipboard)
    component = fixture.componentInstance
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should countdown notification', fakeAsync(() => {
    component.notification = notification2
    fixture.detectChanges()
    component.onShown(notification2)
    tick(5000)
    expect(component.notification.delayRemaining).toEqual(0)
    flush()
    discardPeriodicTasks()
  }))

  it('should show an error if given with notification', fakeAsync(() => {
    component.notification = notification1
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain('Error 1 content')

    flush()
    discardPeriodicTasks()
  }))

  it('should show error details, support copy', fakeAsync(() => {
    component.notification = notification2
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain(
      'Error 2 message details'
    )

    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyError(notification2.error)
    expect(copySpy).toHaveBeenCalled()

    flush()
    discardPeriodicTasks()
  }))

  it('should parse error text, add ellipsis', () => {
    expect(component.getErrorText(notification2.error)).toEqual(
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
