import { ComponentFixture, TestBed } from '@angular/core/testing'

import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { HotkeyDialogComponent } from './hotkey-dialog.component'

describe('HotkeyDialogComponent', () => {
  let component: HotkeyDialogComponent
  let fixture: ComponentFixture<HotkeyDialogComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [HotkeyDialogComponent],
      providers: [NgbActiveModal],
    }).compileComponents()

    fixture = TestBed.createComponent(HotkeyDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should support close', () => {
    const closeSpy = jest.spyOn(component.activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should format keys', () => {
    expect(component.formatKey('control.a')).toEqual('&#8963; + a') // ⌃ + a
    expect(component.formatKey('control.a', true)).toEqual('&#8984; + a') // ⌘ + a
  })
})
