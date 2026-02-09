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
    ;(permissionsService.currentUserCan as jest.Mock).mockImplementation(
      (action, type) => {
        return action === PermissionAction.View && type === PermissionType.Tag
      }
    )

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({}))

    expect(router.navigate).toHaveBeenCalledWith(['attributes', 'tags'], {
      replaceUrl: true,
    })
    expect(component.activeNavID).toBe(1)
  })

  it('should set active section from route param when valid', () => {
    ;(permissionsService.currentUserCan as jest.Mock).mockImplementation(
      (action, type) => {
        return (
          action === PermissionAction.View &&
          type === PermissionType.CustomField
        )
      }
    )

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({ section: 'customfields' }))

    expect(component.activeNavID).toBe(2)
    expect(router.navigate).not.toHaveBeenCalled()
  })

  it('should redirect to dashboard when no sections are visible', () => {
    ;(permissionsService.currentUserCan as jest.Mock).mockReturnValue(false)

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({}))

    expect(router.navigate).toHaveBeenCalledWith(['/dashboard'], {
      replaceUrl: true,
    })
  })

  it('should navigate when a nav change occurs', () => {
    ;(permissionsService.currentUserCan as jest.Mock).mockImplementation(
      () => true
    )

    fixture.detectChanges()
    paramMapSubject.next(convertToParamMap({ section: 'tags' }))

    component.onNavChange({ nextId: 2 } as any)

    expect(router.navigate).toHaveBeenCalledWith(['attributes', 'customfields'])
  })
})
