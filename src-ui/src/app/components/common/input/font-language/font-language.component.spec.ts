import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { FontLanguageComponent } from './font-language.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { NgSelectModule } from '@ng-select/ng-select'
import { GroupService } from 'src/app/services/rest/group.service'
import { of } from 'rxjs'
import { UserService } from 'src/app/services/rest/user.service'

describe('PermissionsUserComponent', () => {
  let component: FontLanguageComponent
  let fixture: ComponentFixture<FontLanguageComponent>
  let userService: UserService
  let userServiceSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [FontLanguageComponent],
      providers: [UserService],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        HttpClientTestingModule,
        NgSelectModule,
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
    fixture = TestBed.createComponent(FontLanguageComponent)
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
