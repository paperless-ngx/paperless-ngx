import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ShareLinksComponent, ShareLinksNavIDs } from './share-links.component'

describe('ShareLinksComponent', () => {
  let fixture: ComponentFixture<ShareLinksComponent>
  let permissionsService: PermissionsService
  let router: Router

  const configure = async (type: string = null) => {
    await TestBed.configureTestingModule({
      imports: [
        ShareLinksComponent,
        NgbNavModule,
        NgxBootstrapIconsModule.pick(allIcons),
        PageHeaderComponent,
      ],
      providers: [
        PermissionsService,
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: convertToParamMap({ type }) },
          },
        },
        {
          provide: Router,
          useValue: { navigate: jest.fn().mockResolvedValue(true) },
        },
      ],
    }).compileComponents()

    permissionsService = TestBed.inject(PermissionsService)
    router = TestBed.inject(Router)
  }

  afterEach(() => TestBed.resetTestingModule())

  it('uses the requested bundles tab when permitted', async () => {
    await configure(ShareLinksNavIDs.Bundles)
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation(
        (action, type) =>
          action === PermissionAction.View &&
          type === PermissionType.ShareLinkBundle
      )

    fixture = TestBed.createComponent(ShareLinksComponent)
    fixture.detectChanges()

    expect(fixture.componentInstance.activeNavID()).toBe(
      ShareLinksNavIDs.Bundles
    )
    expect(fixture.nativeElement.textContent).not.toContain('Document links')
  })

  it('updates the URL when a tab is selected', async () => {
    await configure()
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)

    fixture = TestBed.createComponent(ShareLinksComponent)
    fixture.componentInstance.selectTab(ShareLinksNavIDs.Bundles)

    expect(router.navigate).toHaveBeenCalledWith([], {
      relativeTo: TestBed.inject(ActivatedRoute),
      queryParams: { type: ShareLinksNavIDs.Bundles },
      queryParamsHandling: 'merge',
    })
  })
})
