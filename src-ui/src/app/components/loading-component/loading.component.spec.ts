import { Component } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { LoadingComponentWithPermissions } from './loading.component'

class MockComponentWithPermissions extends ComponentWithPermissions {}

@Component({
  template: '',
})
class MockLoadingComponent extends LoadingComponentWithPermissions {}

describe('LoadingComponentWithPermissions', () => {
  let component: LoadingComponentWithPermissions

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [LoadingComponentWithPermissions],
    })
    component = new MockLoadingComponent()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should have loading set to true by default', () => {
    expect(component.loading).toBeTruthy()
  })

  it('should have show set to false by default', () => {
    expect(component.show).toBeFalsy()
  })

  it('should call next and complete on unsubscribeNotifier with itself on destroy', () => {
    const nextSpy = jest.spyOn(component['unsubscribeNotifier'], 'next')
    const completeSpy = jest.spyOn(component['unsubscribeNotifier'], 'complete')
    component.ngOnDestroy()
    expect(nextSpy).toHaveBeenCalledWith(component)
    expect(completeSpy).toHaveBeenCalled()
  })
})
