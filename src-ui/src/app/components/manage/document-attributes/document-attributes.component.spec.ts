import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  ActivatedRoute,
  convertToParamMap,
  ParamMap,
  Router,
} from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import {
  DocumentAttributesComponent,
  DocumentAttributesSectionKind,
} from './document-attributes.component'

@Component({
  selector: 'pngx-dummy-section',
  template: '',
  standalone: true,
})
class DummySectionComponent {}

describe('DocumentAttributesComponent', () => {
  let component: DocumentAttributesComponent
  let fixture: ComponentFixture<DocumentAttributesComponent>
  let router: Router
  let paramMapSubject: Subject<ParamMap>
  let permissionsService: PermissionsService

  beforeEach(async () => {
    paramMapSubject = new Subject<ParamMap>()

    TestBed.configureTestingModule({
      imports: [
        RouterTestingModule,
        NgxBootstrapIconsModule.pick(allIcons),
        DocumentAttributesComponent,
        DummySectionComponent,
      ],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: paramMapSubject.asObservable(),
          },
        },
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: jest.fn(),
          },
        },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentAttributesComponent)
    component = fixture.componentInstance
    router = TestBed.inject(Router)
    permissionsService = TestBed.inject(PermissionsService)

    jest.spyOn(router, 'navigate').mockResolvedValue(true)
    ;(component as any).sections = [
      {
        id: 1,
        path: 'tags',
        label: 'Tags',
        icon: 'tags',
        permissionType: PermissionType.Tag,
        kind: DocumentAttributesSectionKind.ManagementList,
        component: DummySectionComponent,
      },
      {
        id: 2,
        path: 'customfields',
        label: 'Custom fields',
        icon: 'ui-radios',
        permissionType: PermissionType.CustomField,
        kind: DocumentAttributesSectionKind.CustomFields,
        component: DummySectionComponent,
      },
    ]
  })

  it('should navigate to default section when no section is provided', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return action === PermissionAction.View && type === PermissionType.Tag
      })

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({}))

    expect(router.navigate).toHaveBeenCalledWith(['attributes', 'tags'], {
      replaceUrl: true,
    })
    expect(component.activeNavID).toBe(1)
  })

  it('should set active section from route param when valid', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        return (
          action === PermissionAction.View &&
          type === PermissionType.CustomField
        )
      })

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({ section: 'customfields' }))

    expect(component.activeNavID).toBe(2)
    expect(router.navigate).not.toHaveBeenCalled()
  })

  it('should update active nav id when route section changes', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    fixture.detectChanges()
    component.activeNavID = 1
    paramMapSubject.next(convertToParamMap({ section: 'customfields' }))

    expect(component.activeNavID).toBe(2)
  })

  it('should redirect to dashboard when no sections are visible', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({}))

    expect(router.navigate).toHaveBeenCalledWith(['/dashboard'], {
      replaceUrl: true,
    })
  })

  it('should navigate when a nav change occurs', () => {
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation(() => true)

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({ section: 'tags' }))

    component.onNavChange({ nextId: 2 } as any)

    expect(router.navigate).toHaveBeenCalledWith(['attributes', 'customfields'])
  })

  it('should ignore nav changes for unknown sections', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({ section: 'tags' }))

    component.onNavChange({ nextId: 999 } as any)

    expect(router.navigate).not.toHaveBeenCalled()
  })

  it('should return activeManagementList correctly', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.activeManagementList).toBeNull()

    component.activeNavID = 1
    expect(component.activeSection.kind).toBe(
      DocumentAttributesSectionKind.ManagementList
    )
    expect(component.activeManagementList).toBeDefined()
  })

  it('should return activeCustomFields correctly', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.activeCustomFields).toBeNull()

    component.activeNavID = 2
    expect(component.activeSection.kind).toBe(
      DocumentAttributesSectionKind.CustomFields
    )
    expect(component.activeCustomFields).toBeDefined()
  })
})
