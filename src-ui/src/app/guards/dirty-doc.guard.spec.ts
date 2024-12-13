import { Component } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { NgbModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { routes } from '../app-routing.module'
import { ComponentCanDeactivate, DirtyDocGuard } from './dirty-doc.guard'

@Component({})
class GenericDirtyDocComponent implements ComponentCanDeactivate {
  canDeactivate: () => boolean
}

describe('DirtyDocGuard', () => {
  let guard: DirtyDocGuard
  let component: ComponentCanDeactivate

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [DirtyDocGuard, NgbModal, GenericDirtyDocComponent],
      imports: [RouterTestingModule.withRoutes(routes), NgbModule],
      declarations: [GenericDirtyDocComponent],
    }).compileComponents()

    guard = TestBed.inject(DirtyDocGuard)
    const fixture = TestBed.createComponent(GenericDirtyDocComponent)
    component = fixture.componentInstance
    window.confirm = jest.fn().mockImplementation(() => true)

    fixture.detectChanges()
  })

  it('should deactivate if component is not dirty', () => {
    component.canDeactivate = () => true
    const confirmSpy = jest.spyOn(window, 'confirm')
    const canDeactivate = guard.canDeactivate(component)

    expect(canDeactivate).toBeTruthy()
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('should not deactivate if component is dirty', () => {
    component.canDeactivate = () => false
    const confirmSpy = jest.spyOn(window, 'confirm')
    const canDeactivate = guard.canDeactivate(component)

    expect(confirmSpy).toHaveBeenCalled()
  })
})
