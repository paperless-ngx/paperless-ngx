import { NgComponentOutlet } from '@angular/common'
import {
  AfterViewChecked,
  ChangeDetectorRef,
  Component,
  inject,
  OnDestroy,
  OnInit,
  Type,
  ViewChild,
} from '@angular/core'
import { ActivatedRoute, Router } from '@angular/router'
import {
  NgbDropdownModule,
  NgbNavChangeEvent,
  NgbNavModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { ClearableBadgeComponent } from '../../common/clearable-badge/clearable-badge.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { CustomFieldsComponent } from './custom-fields/custom-fields.component'
import { CorrespondentListComponent } from './management-list/correspondent-list/correspondent-list.component'
import { DocumentTypeListComponent } from './management-list/document-type-list/document-type-list.component'
import { ManagementListComponent } from './management-list/management-list.component'
import { StoragePathListComponent } from './management-list/storage-path-list/storage-path-list.component'
import { TagListComponent } from './management-list/tag-list/tag-list.component'

enum DocumentAttributesNavIDs {
  Tags = 1,
  Correspondents = 2,
  DocumentTypes = 3,
  StoragePaths = 4,
  CustomFields = 5,
}

export enum DocumentAttributesSectionKind {
  ManagementList = 'managementList',
  CustomFields = 'customFields',
}

interface DocumentAttributesSection {
  id: DocumentAttributesNavIDs
  path: string
  label: string
  icon: string
  infoLink?: string
  permissionType: PermissionType
  kind: DocumentAttributesSectionKind
  component: Type<any>
}

@Component({
  selector: 'pngx-document-attributes',
  templateUrl: './document-attributes.component.html',
  styleUrls: ['./document-attributes.component.scss'],
  imports: [
    PageHeaderComponent,
    NgbNavModule,
    NgbDropdownModule,
    NgComponentOutlet,
    NgxBootstrapIconsModule,
    IfPermissionsDirective,
    ClearableBadgeComponent,
  ],
})
export class DocumentAttributesComponent
  implements OnInit, OnDestroy, AfterViewChecked
{
  private readonly permissionsService = inject(PermissionsService)
  private readonly activatedRoute = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly cdr = inject(ChangeDetectorRef)
  private readonly unsubscribeNotifier = new Subject<void>()

  protected readonly PermissionAction = PermissionAction
  protected readonly PermissionType = PermissionType

  readonly sections: DocumentAttributesSection[] = [
    {
      id: DocumentAttributesNavIDs.Tags,
      path: 'tags',
      label: $localize`Tags`,
      icon: 'tags',
      infoLink: 'usage/#terms-and-definitions',
      permissionType: PermissionType.Tag,
      kind: DocumentAttributesSectionKind.ManagementList,
      component: TagListComponent,
    },
    {
      id: DocumentAttributesNavIDs.Correspondents,
      path: 'correspondents',
      label: $localize`Correspondents`,
      icon: 'person',
      infoLink: 'usage/#terms-and-definitions',
      permissionType: PermissionType.Correspondent,
      kind: DocumentAttributesSectionKind.ManagementList,
      component: CorrespondentListComponent,
    },
    {
      id: DocumentAttributesNavIDs.DocumentTypes,
      path: 'documenttypes',
      label: $localize`Document types`,
      icon: 'hash',
      infoLink: 'usage/#terms-and-definitions',
      permissionType: PermissionType.DocumentType,
      kind: DocumentAttributesSectionKind.ManagementList,
      component: DocumentTypeListComponent,
    },
    {
      id: DocumentAttributesNavIDs.StoragePaths,
      path: 'storagepaths',
      label: $localize`Storage paths`,
      icon: 'folder',
      infoLink: 'usage/#terms-and-definitions',
      permissionType: PermissionType.StoragePath,
      kind: DocumentAttributesSectionKind.ManagementList,
      component: StoragePathListComponent,
    },
    {
      id: DocumentAttributesNavIDs.CustomFields,
      path: 'customfields',
      label: $localize`Custom fields`,
      icon: 'ui-radios',
      infoLink: 'usage/#custom-fields',
      permissionType: PermissionType.CustomField,
      kind: DocumentAttributesSectionKind.CustomFields,
      component: CustomFieldsComponent,
    },
  ]

  @ViewChild('activeOutlet', { read: NgComponentOutlet })
  private readonly activeOutlet?: NgComponentOutlet

  private lastHeaderLoading: boolean

  activeNavID: number = null

  get visibleSections(): DocumentAttributesSection[] {
    return this.sections.filter((section) =>
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        section.permissionType
      )
    )
  }

  get activeSection(): DocumentAttributesSection | null {
    return (
      this.visibleSections.find((section) => section.id === this.activeNavID) ??
      null
    )
  }

  get activeManagementList(): ManagementListComponent<any> | null {
    if (
      this.activeSection?.kind !== DocumentAttributesSectionKind.ManagementList
    )
      return null
    const instance = this.activeOutlet?.componentInstance
    return instance instanceof ManagementListComponent ? instance : null
  }

  get activeCustomFields(): CustomFieldsComponent | null {
    if (this.activeSection?.kind !== DocumentAttributesSectionKind.CustomFields)
      return null
    const instance = this.activeOutlet?.componentInstance
    return instance instanceof CustomFieldsComponent ? instance : null
  }

  get activeTabLabel(): string {
    return this.activeSection?.label ?? ''
  }

  get activeInfoLink(): string {
    return this.activeSection?.infoLink ?? null
  }

  get activeHeaderLoading(): boolean {
    return (
      this.activeManagementList?.loading ??
      this.activeCustomFields?.loading ??
      false
    )
  }

  ngOnInit(): void {
    this.activatedRoute.paramMap
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((paramMap) => {
        const section = paramMap.get('section')
        const navIDFromSection =
          this.getNavIDForSection(section) ?? this.getDefaultNavID()

        if (navIDFromSection == null) {
          this.router.navigate(['/dashboard'], { replaceUrl: true })
          return
        }

        if (this.activeNavID !== navIDFromSection) {
          this.activeNavID = navIDFromSection
        }

        if (!section || this.getNavIDForSection(section) == null) {
          this.router.navigate(
            ['attributes', this.getSectionForNavID(this.activeNavID)],
            { replaceUrl: true }
          )
        }
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  ngAfterViewChecked(): void {
    const current = this.activeHeaderLoading
    if (this.lastHeaderLoading !== current) {
      this.lastHeaderLoading = current
      this.cdr.detectChanges()
    }
  }

  onNavChange(navChangeEvent: NgbNavChangeEvent): void {
    const nextSection = this.getSectionForNavID(navChangeEvent.nextId)
    if (!nextSection) {
      return
    }
    this.router.navigate(['attributes', nextSection])
  }

  private getDefaultNavID(): DocumentAttributesNavIDs | null {
    return this.visibleSections[0]?.id ?? null
  }

  private getNavIDForSection(section: string): DocumentAttributesNavIDs | null {
    const path = section?.toLowerCase()
    if (!path) return null

    const found = this.visibleSections.find((s) => s.path === path)
    return found?.id ?? null
  }

  private getSectionForNavID(navID: number): string | null {
    const section = this.visibleSections.find((s) => s.id === navID)
    return section?.path ?? null
  }
}
