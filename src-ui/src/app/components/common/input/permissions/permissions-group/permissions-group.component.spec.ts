import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
import { GroupService } from 'src/app/services/rest/group.service'
import { PermissionsGroupComponent } from './permissions-group.component'

describe('PermissionsGroupComponent', () => {
  let component: PermissionsGroupComponent
  let fixture: ComponentFixture<PermissionsGroupComponent>
  let groupService: GroupService
  let groupServiceSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PermissionsGroupComponent],
      imports: [FormsModule, ReactiveFormsModule, NgSelectModule],
      providers: [
        GroupService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    groupService = TestBed.inject(GroupService)
    groupServiceSpy = jest.spyOn(groupService, 'listAll').mockReturnValue(
      of({
        count: 2,
        all: [2, 3],
        results: [
          {
            id: 2,
            name: 'Group 2',
          },
          {
            id: 3,
            name: 'Group 3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(PermissionsGroupComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should get groups, support use of select', () => {
    component.writeValue({ id: 2, name: 'Group 2' })
    expect(component.value).toEqual({ id: 2, name: 'Group 2' })
    expect(groupServiceSpy).toHaveBeenCalled()
  })
})
