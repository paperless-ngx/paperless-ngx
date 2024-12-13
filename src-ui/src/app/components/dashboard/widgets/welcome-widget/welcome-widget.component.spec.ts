import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgbAlert, NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'
import { WelcomeWidgetComponent } from './welcome-widget.component'

describe('WelcomeWidgetComponent', () => {
  let component: WelcomeWidgetComponent
  let fixture: ComponentFixture<WelcomeWidgetComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [WelcomeWidgetComponent, WidgetFrameComponent],
      providers: [PermissionsGuard],
      imports: [NgbAlertModule],
    }).compileComponents()

    fixture = TestBed.createComponent(WelcomeWidgetComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should be dismissable', () => {
    let dismissResult
    component.dismiss.subscribe(() => (dismissResult = true))
    fixture.debugElement
      .query(By.directive(NgbAlert))
      .triggerEventHandler('closed')
    expect(dismissResult).toBeTruthy()
  })
})
