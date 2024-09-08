import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { WidgetFrameComponent } from './widget-frame.component'
import { DragDropModule } from '@angular/cdk/drag-drop'

@Component({
  template: `
    <div>
      <button
        *pngxIfObjectPermissions="{
          object: { id: 2, owner: user1 },
          action: 'view',
        }"
      >
        Some Text
      </button>
    </div>
  `,
})
class TestComponent extends WidgetFrameComponent {}

describe('WidgetFrameComponent', () => {
  let component: WidgetFrameComponent
  let fixture: ComponentFixture<WidgetFrameComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [WidgetFrameComponent, WidgetFrameComponent],
      providers: [PermissionsGuard],
      imports: [NgbAlertModule, DragDropModule],
    }).compileComponents()

    fixture = TestBed.createComponent(WidgetFrameComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should show title', () => {
    component.title = 'Foo'
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain('Foo')
  })

  it('should show loading indicator', () => {
    expect(fixture.debugElement.query(By.css('.spinner-border'))).toBeNull()
    component.loading = true
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('.spinner-border'))).not.toBeNull()
  })
})
