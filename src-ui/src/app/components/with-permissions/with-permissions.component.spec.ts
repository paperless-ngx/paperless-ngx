import { TestBed } from '@angular/core/testing'
import { ComponentWithPermissions } from './with-permissions.component'

describe('ComponentWithPermissions', () => {
  let component: ComponentWithPermissions

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ComponentWithPermissions],
    })
  })

  it('should include permissions classes', () => {
    component = new ComponentWithPermissions()
    expect(component.PermissionAction).not.toBeNull()
    expect(component.PermissionType).not.toBeNull()
  })
})
