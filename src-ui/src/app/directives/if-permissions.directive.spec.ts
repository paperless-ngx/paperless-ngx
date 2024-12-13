import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { PermissionsService } from '../services/permissions.service'
import { IfPermissionsDirective } from './if-permissions.directive'

@Component({
  template: `
    <div>
      <button *pngxIfPermissions="{ action: 'add', type: '%s_user' }">
        Some Text
      </button>
    </div>
  `,
})
class TestComponent {}

describe('IfPermissionsDirective', () => {
  let fixture: ComponentFixture<TestComponent>
  let permissionsService: PermissionsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [IfPermissionsDirective, TestComponent],
      providers: [PermissionsService],
    })
    permissionsService = TestBed.inject(PermissionsService)
  })

  it('should create element if user has permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockImplementation(() => {
      return true
    })

    fixture = TestBed.createComponent(TestComponent)

    fixture.detectChanges()

    const rootEl = (fixture.nativeElement as HTMLDivElement).children[0]
    expect(rootEl.querySelectorAll('button').length).toEqual(1)
  })

  it('should not create element if user has does not have permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockImplementation(() => {
      return false
    })

    fixture = TestBed.createComponent(TestComponent)

    fixture.detectChanges()

    const rootEl = (fixture.nativeElement as HTMLDivElement).children[0]
    expect(rootEl.querySelectorAll('button').length).toEqual(0)
  })
})
