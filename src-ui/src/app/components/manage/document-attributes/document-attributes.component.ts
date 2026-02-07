import { NgComponentOutlet } from '@angular/common'
import {
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
import { CustomFieldsComponent } from '../custom-fields/custom-fields.component'
import { CorrespondentListComponent } from '../management-list/correspondent-list/correspondent-list.component'
import { DocumentTypeListComponent } from '../management-list/document-type-list/document-type-list.component'
import { ManagementListComponent } from '../management-list/management-list.component'
import { StoragePathListComponent } from '../management-list/storage-path-list/storage-path-list.component'
import { TagListComponent } from '../management-list/tag-list/tag-list.component'

enum DocumentAttributesNavIDs {
  Tags = 1,
  Correspondents = 2,
  DocumentTypes = 3,
  StoragePaths = 4,
  CustomFields = 5,
}

type DocumentAttributesTabKind = 'bulk' | 'customFields'

interface DocumentAttributesTab {
  id: DocumentAttributesNavIDs
  section: string
  label: string
  icon: string
  permissionType: PermissionType
  kind: DocumentAttributesTabKind
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
export class DocumentAttributesComponent implements OnInit, OnDestroy {
  private readonly permissionsService = inject(PermissionsService)
  private readonly activatedRoute = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly unsubscribeNotifier = new Subject<void>()

  protected readonly PermissionAction = PermissionAction
  protected readonly PermissionType = PermissionType

  readonly tabs: DocumentAttributesTab[] = [
    {
      id: DocumentAttributesNavIDs.Tags,
      section: 'tags',
      label: $localize`Tags`,
      icon: 'tags',
      permissionType: PermissionType.Tag,
      kind: 'bulk',
      component: TagListComponent,
    },
    {
      id: DocumentAttributesNavIDs.Correspondents,
      section: 'correspondents',
      label: $localize`Correspondents`,
      icon: 'person',
      permissionType: PermissionType.Correspondent,
      kind: 'bulk',
      component: CorrespondentListComponent,
    },
    {
      id: DocumentAttributesNavIDs.DocumentTypes,
      section: 'documenttypes',
      label: $localize`Document types`,
      icon: 'hash',
      permissionType: PermissionType.DocumentType,
      kind: 'bulk',
      component: DocumentTypeListComponent,
    },
    {
      id: DocumentAttributesNavIDs.StoragePaths,
      section: 'storagepaths',
      label: $localize`Storage paths`,
      icon: 'folder',
      permissionType: PermissionType.StoragePath,
      kind: 'bulk',
      component: StoragePathListComponent,
    },
    {
      id: DocumentAttributesNavIDs.CustomFields,
      section: 'customfields',
      label: $localize`Custom fields`,
      icon: 'ui-radios',
      permissionType: PermissionType.CustomField,
      kind: 'customFields',
      component: CustomFieldsComponent,
    },
  ]

  @ViewChild(TagListComponent) private tagList?: TagListComponent
  @ViewChild(CorrespondentListComponent)
  private correspondentList?: CorrespondentListComponent
  @ViewChild(DocumentTypeListComponent)
  private documentTypeList?: DocumentTypeListComponent
  @ViewChild(StoragePathListComponent)
  private storagePathList?: StoragePathListComponent
  @ViewChild(CustomFieldsComponent)
  private customFields?: CustomFieldsComponent

  activeNavID: number = null

  get visibleTabs(): DocumentAttributesTab[] {
    return this.tabs.filter((tab) =>
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        tab.permissionType
      )
    )
  }

  get activeTab(): DocumentAttributesTab | null {
    return this.visibleTabs.find((t) => t.id === this.activeNavID) ?? null
  }

  get activeBulkList(): ManagementListComponent<any> | null {
    switch (this.activeNavID) {
      case DocumentAttributesNavIDs.Tags:
        return this.tagList ?? null
      case DocumentAttributesNavIDs.Correspondents:
        return this.correspondentList ?? null
      case DocumentAttributesNavIDs.DocumentTypes:
        return this.documentTypeList ?? null
      case DocumentAttributesNavIDs.StoragePaths:
        return this.storagePathList ?? null
      default:
        return null
    }
  }

  get activeCustomFields(): CustomFieldsComponent | null {
    return this.activeNavID === DocumentAttributesNavIDs.CustomFields
      ? (this.customFields ?? null)
      : null
  }

  get activeTabLabel(): string {
    return this.activeTab?.label ?? ''
  }

  get activeHeaderLoading(): boolean {
    return (
      this.activeBulkList?.loading ?? this.activeCustomFields?.loading ?? false
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

  onNavChange(navChangeEvent: NgbNavChangeEvent): void {
    const nextSection = this.getSectionForNavID(navChangeEvent.nextId)
    if (!nextSection) {
      return
    }
    this.router.navigate(['attributes', nextSection])
  }

  private getDefaultNavID(): DocumentAttributesNavIDs | null {
    return this.visibleTabs[0]?.id ?? null
  }

  private getNavIDForSection(section: string): DocumentAttributesNavIDs | null {
    const sectionKey = section?.toLowerCase()
    if (!sectionKey) return null

    const tab = this.visibleTabs.find((t) => t.section === sectionKey)
    return tab?.id ?? null
  }

  private getSectionForNavID(navID: number): string | null {
    const tab = this.visibleTabs.find((t) => t.id === navID)
    return tab?.section ?? null
  }
}
