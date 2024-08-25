import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  ReactiveFormsModule,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { PermissionsFormComponent } from './permissions-form.component'
import { SelectComponent } from '../../select/select.component'
import { NgbAccordionModule } from '@ng-bootstrap/ng-bootstrap'
import { PermissionsGroupComponent } from '../permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../permissions-user/permissions-user.component'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { NgSelectModule } from '@ng-select/ng-select'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('PermissionsFormComponent', () => {
  let component: PermissionsFormComponent
  let fixture: ComponentFixture<PermissionsFormComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        PermissionsFormComponent,
        SelectComponent,
        PermissionsGroupComponent,
        PermissionsUserComponent,
      ],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgbAccordionModule,
        NgSelectModule,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(PermissionsFormComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support use of select for owner', () => {
    const changeSpy = jest.spyOn(component, 'onChange')
    component.ngOnInit()
    component.users = [
      {
        id: 2,
        username: 'foo',
      },
      {
        id: 3,
        username: 'bar',
      },
    ]
    component.form.get('owner').patchValue(2)
    fixture.detectChanges()
    expect(changeSpy).toHaveBeenCalledWith({
      owner: 2,
      set_permissions: {
        view: { users: [], groups: [] },
        change: { users: [], groups: [] },
      },
    })
  })
})
