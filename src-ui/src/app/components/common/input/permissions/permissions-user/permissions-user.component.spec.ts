import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { PermissionsUserComponent } from './permissions-user.component'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { NgSelectModule } from '@ng-select/ng-select'
import { GroupService } from 'src/app/services/rest/group.service'
import { of } from 'rxjs'
import { UserService } from 'src/app/services/rest/user.service'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('PermissionsUserComponent', () => {
  let component: PermissionsUserComponent
  let fixture: ComponentFixture<PermissionsUserComponent>
  let userService: UserService
  let userServiceSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PermissionsUserComponent],
      imports: [FormsModule, ReactiveFormsModule, NgSelectModule],
      providers: [
        UserService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    userService = TestBed.inject(UserService)
    userServiceSpy = jest.spyOn(userService, 'listAll').mockReturnValue(
      of({
        count: 2,
        all: [2, 3],
        results: [
          {
            id: 2,
            name: 'User 2',
          },
          {
            id: 3,
            name: 'User 3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(PermissionsUserComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should get users, support use of select', () => {
    component.writeValue({ id: 2, name: 'User 2' })
    expect(component.value).toEqual({ id: 2, name: 'User 2' })
    expect(userServiceSpy).toHaveBeenCalled()
  })
})
