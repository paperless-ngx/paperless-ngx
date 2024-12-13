import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { PermissionsService } from '../services/permissions.service'
import { IfOwnerDirective } from './if-owner.directive'

@Component({
  template: `
    <div>
      <button *pngxIfOwner="{ id: 2, owner: user1 }">Some Text</button>
    </div>
  `,
})
class TestComponent {}

describe('IfOwnerDirective', () => {
  let fixture: ComponentFixture<TestComponent>
  let permissionsService: PermissionsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [IfOwnerDirective, TestComponent],
      providers: [PermissionsService],
    })
    permissionsService = TestBed.inject(PermissionsService)
  })

  it('should create element if user owns object', () => {
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockImplementation(() => {
        return true
      })

    fixture = TestBed.createComponent(TestComponent)

    fixture.detectChanges()

    const rootEl = (fixture.nativeElement as HTMLDivElement).children[0]
    expect(rootEl.querySelectorAll('button').length).toEqual(1)
  })

  it('should not create element if user does not own object', () => {
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockImplementation(() => {
        return false
      })

    fixture = TestBed.createComponent(TestComponent)

    fixture.detectChanges()

    const rootEl = (fixture.nativeElement as HTMLDivElement).children[0]
    expect(rootEl.querySelectorAll('button').length).toEqual(0)
  })
})
