import { ComponentFixture, TestBed } from '@angular/core/testing'

import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from './confirm-button.component'

describe('ConfirmButtonComponent', () => {
  let component: ConfirmButtonComponent
  let fixture: ComponentFixture<ConfirmButtonComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ConfirmButtonComponent],
      imports: [NgbPopoverModule, NgxBootstrapIconsModule.pick(allIcons)],
    }).compileComponents()

    fixture = TestBed.createComponent(ConfirmButtonComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should show confirm on click', () => {
    expect(component.popover.isOpen()).toBeFalsy()
    expect(component.confirming).toBeFalsy()
    component.onClick(new MouseEvent('click'))
    expect(component.popover.isOpen()).toBeTruthy()
    expect(component.confirming).toBeTruthy()
  })

  it('should emit confirm on confirm', () => {
    const confirmSpy = jest.spyOn(component.confirm, 'emit')
    component.onConfirm(new MouseEvent('click'))
    expect(confirmSpy).toHaveBeenCalled()
    expect(component.popover.isOpen()).toBeFalsy()
    expect(component.confirming).toBeFalsy()
  })
})
