import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { ExportTarget, ExportTargetKind } from 'src/app/data/export-target'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { ExportTargetService } from 'src/app/services/rest/export-target.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ExportTargetEditDialogComponent } from '../../common/edit-dialog/export-target-edit-dialog/export-target-edit-dialog.component'
import { ExportTargetsComponent } from './export-targets.component'

const targets: ExportTarget[] = [
  {
    id: 1,
    name: 'Bucket',
    kind: ExportTargetKind.S3,
    config: { bucket: 'docs', prefix: 'paperless' },
    enabled: true,
  },
  {
    id: 2,
    name: 'NAS',
    kind: ExportTargetKind.SFTP,
    config: { host: 'nas.local', path: '/exports' },
    enabled: false,
  },
]

describe('ExportTargetsComponent', () => {
  let component: ExportTargetsComponent
  let fixture: ComponentFixture<ExportTargetsComponent>
  let httpController: HttpTestingController
  let modalService: NgbModal
  let toastService: ToastService
  let permissionsService: PermissionsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        ExportTargetsComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    httpController = TestBed.inject(HttpTestingController)
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)
    permissionsService = TestBed.inject(PermissionsService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockReturnValue(true)

    fixture = TestBed.createComponent(ExportTargetsComponent)
    component = fixture.componentInstance
    fixture.detectChanges()

    httpController
      .expectOne(
        `${environment.apiBaseUrl}export_targets/?page=1&page_size=100000&full_perms=true`
      )
      .flush({ count: targets.length, results: targets })
    fixture.detectChanges()
  })

  it('should list targets', () => {
    expect(component.exportTargets()).toHaveLength(2)
    expect(fixture.nativeElement.textContent).toContain('Bucket')
    expect(fixture.nativeElement.textContent).toContain('NAS')
    expect(fixture.nativeElement.textContent).toContain('Paused')
  })

  it('should format destinations per kind', () => {
    expect(component.destination(targets[0])).toEqual('docs/paperless')
    expect(component.destination(targets[1])).toEqual('nas.local:/exports')
    expect(
      component.destination({
        id: 3,
        name: 'Dir',
        kind: ExportTargetKind.Local,
        config: { path: '/mnt/export' },
        enabled: true,
      })
    ).toEqual('/mnt/export')
  })

  it('should support edit dialog', () => {
    const modal = { componentInstance: {} } as any
    const openSpy = jest.spyOn(modalService, 'open')
    component.editTarget(targets[0])
    expect(openSpy).toHaveBeenCalledWith(
      ExportTargetEditDialogComponent,
      expect.anything()
    )
  })

  it('should support delete with confirm', () => {
    let modal
    modalService.activeInstances.subscribe((instances) => {
      modal = instances[0]
    })
    const deleteSpy = jest.spyOn(TestBed.inject(ExportTargetService), 'delete')
    deleteSpy.mockReturnValue(of(true))
    component.deleteTarget(targets[0])
    expect(modal).not.toBeUndefined()
    const confirmDialog = modal.componentInstance as ConfirmDialogComponent
    confirmDialog.confirmClicked.emit()
    expect(deleteSpy).toHaveBeenCalled()
    httpController
      .expectOne(
        `${environment.apiBaseUrl}export_targets/?page=1&page_size=100000&full_perms=true`
      )
      .flush({ count: targets.length, results: targets })
  })
})
