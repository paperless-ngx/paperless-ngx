import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { Component } from '@angular/core'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import {
  FormGroup,
  FormControl,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { of } from 'rxjs'
import {
  DEFAULT_MATCHING_ALGORITHM,
  MATCH_AUTO,
  MATCH_NONE,
  MATCH_ALL,
} from 'src/app/data/matching-model'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { TagService } from 'src/app/services/rest/tag.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'
import { EditDialogComponent, EditDialogMode } from './edit-dialog.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

@Component({
  template: `
    <div>
      <h4 class="modal-title" id="modal-basic-title">{{ getTitle() }}</h4>
    </div>
  `,
})
class TestComponent extends EditDialogComponent<Tag> {
  constructor(
    service: TagService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getForm(): FormGroup<any> {
    return new FormGroup({
      name: new FormControl(''),
      color: new FormControl(''),
      is_inbox_tag: new FormControl(false),
      permissions_form: new FormControl(null),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
    })
  }
}

const currentUser = {
  id: 99,
  username: 'user99',
}

const permissions = {
  view: {
    users: [11],
    groups: [],
  },
  change: {
    users: [],
    groups: [2],
  },
}

const tag = {
  id: 1,
  name: 'Tag 1',
  color: '#fff000',
  is_inbox_tag: false,
  matching_algorithm: MATCH_AUTO,
  owner: 10,
  permissions,
}

describe('EditDialogComponent', () => {
  let component: TestComponent
  let fixture: ComponentFixture<TestComponent>
  let tagService: TagService
  let settingsService: SettingsService
  let activeModal: NgbActiveModal
  let httpTestingController: HttpTestingController

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [TestComponent],
      imports: [FormsModule, ReactiveFormsModule],
      providers: [
        NgbActiveModal,
        {
          provide: UserService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 13,
                    username: 'user1',
                  },
                ],
              }),
          },
        },
        SettingsService,
        TagService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    tagService = TestBed.inject(TagService)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = currentUser
    activeModal = TestBed.inject(NgbActiveModal)
    httpTestingController = TestBed.inject(HttpTestingController)

    fixture = TestBed.createComponent(TestComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should interpolate object permissions', () => {
    component.getMatchingAlgorithms() // coverage
    component.object = tag
    component.dialogMode = EditDialogMode.EDIT
    component.ngOnInit()

    expect(component.objectForm.get('permissions_form').value).toEqual({
      owner: tag.owner,
      set_permissions: permissions,
    })
  })

  it('should delay close enabled', fakeAsync(() => {
    expect(component.closeEnabled).toBeFalsy()
    component.ngOnInit()
    tick(100)
    expect(component.closeEnabled).toBeTruthy()
  }))

  it('should set default owner when in create mode if unset', () => {
    component.dialogMode = EditDialogMode.CREATE
    component.ngOnInit()
    expect(component.objectForm.get('permissions_form').value.owner).toEqual(
      currentUser.id
    )
    // cover optional chaining
    component.objectForm.removeControl('permissions_form')
    component.ngOnInit()
  })

  it('should set default perms when in create mode if set', () => {
    component.dialogMode = EditDialogMode.CREATE
    settingsService.set(SETTINGS_KEYS.DEFAULT_PERMS_OWNER, 11)
    settingsService.set(SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS, [1, 2])
    settingsService.set(SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS, [3])
    settingsService.set(SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS, [4])
    settingsService.set(SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS, [5])
    component.ngOnInit()
    expect(component.objectForm.get('permissions_form').value.owner).toEqual(11)
    expect(
      component.objectForm.get('permissions_form').value.set_permissions
    ).toEqual({
      view: {
        users: [1, 2],
        groups: [3],
      },
      change: {
        users: [4],
        groups: [5],
      },
    })
    // cover optional chaining
    component.objectForm.removeControl('permissions_form')
    component.ngOnInit()
  })

  it('should detect if pattern required', () => {
    expect(component.patternRequired).toBeFalsy()
    component.objectForm.get('matching_algorithm').setValue(MATCH_AUTO)
    expect(component.patternRequired).toBeFalsy()
    component.objectForm.get('matching_algorithm').setValue(MATCH_NONE)
    expect(component.patternRequired).toBeFalsy()
    component.objectForm.get('matching_algorithm').setValue(MATCH_ALL)
    expect(component.patternRequired).toBeTruthy()
    // coverage
    component.objectForm = null
    expect(component.patternRequired).toBeTruthy()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
    // coverage
    component.dialogMode = null
    fixture.detectChanges()
  })

  it('should close on cancel', () => {
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.cancel()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should update an object on save in edit mode', () => {
    const updateSpy = jest.spyOn(tagService, 'update')
    component.dialogMode = EditDialogMode.EDIT
    component.save()
    expect(updateSpy).toHaveBeenCalled()
  })

  it('should create an object on save in edit mode', () => {
    const createSpy = jest.spyOn(tagService, 'create')
    component.dialogMode = EditDialogMode.CREATE
    component.save()
    expect(createSpy).toHaveBeenCalled()
  })

  it('should close on successful save', () => {
    const closeSpy = jest.spyOn(activeModal, 'close')
    const successSpy = jest.spyOn(component.succeeded, 'emit')
    component.save()
    httpTestingController.expectOne(`${environment.apiBaseUrl}tags/`).flush({})
    expect(closeSpy).toHaveBeenCalled()
    expect(successSpy).toHaveBeenCalled()
  })

  it('should not close on failed save', () => {
    const closeSpy = jest.spyOn(activeModal, 'close')
    const failedSpy = jest.spyOn(component.failed, 'next')
    component.save()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}tags/`)
      .flush('error', {
        status: 500,
        statusText: 'error',
      })
    expect(closeSpy).not.toHaveBeenCalled()
    expect(failedSpy).toHaveBeenCalled()
    expect(component.error).toEqual('error')
  })
})
