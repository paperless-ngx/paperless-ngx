import { Component, inject, OnDestroy, OnInit, ViewChild } from '@angular/core'
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
import { CorrespondentListComponent } from '../correspondent-list/correspondent-list.component'
import { CustomFieldsComponent } from '../custom-fields/custom-fields.component'
import { DocumentTypeListComponent } from '../document-type-list/document-type-list.component'
import { ManagementListComponent } from '../management-list/management-list.component'
import { StoragePathListComponent } from '../storage-path-list/storage-path-list.component'
import { TagListComponent } from '../tag-list/tag-list.component'

enum DocumentAttributesNavIDs {
  Tags = 1,
  Correspondents = 2,
  DocumentTypes = 3,
  StoragePaths = 4,
  CustomFields = 5,
}

@Component({
  selector: 'pngx-document-attributes',
  templateUrl: './document-attributes.component.html',
  styleUrls: ['./document-attributes.component.scss'],
  imports: [
    PageHeaderComponent,
    NgbNavModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    IfPermissionsDirective,
    ClearableBadgeComponent,
    TagListComponent,
    CorrespondentListComponent,
    DocumentTypeListComponent,
    StoragePathListComponent,
    CustomFieldsComponent,
  ],
})
export class DocumentAttributesComponent implements OnInit, OnDestroy {
  private readonly permissionsService = inject(PermissionsService)
  private readonly activatedRoute = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly unsubscribeNotifier = new Subject<void>()

  protected readonly DocumentAttributesNavIDs = DocumentAttributesNavIDs
  protected readonly PermissionAction = PermissionAction
  protected readonly PermissionType = PermissionType

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
    switch (this.activeNavID) {
      case DocumentAttributesNavIDs.Tags:
        return $localize`Tags`
      case DocumentAttributesNavIDs.Correspondents:
        return $localize`Correspondents`
      case DocumentAttributesNavIDs.DocumentTypes:
        return $localize`Document types`
      case DocumentAttributesNavIDs.StoragePaths:
        return $localize`Storage paths`
      case DocumentAttributesNavIDs.CustomFields:
        return $localize`Custom fields`
      default:
        return ''
    }
  }

  get activeHeaderLoading(): boolean {
    return (
      this.activeBulkList?.loading ?? this.activeCustomFields?.loading ?? false
    )
  }

  get canViewTags(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.Tag
    )
  }

  get canViewCorrespondents(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.Correspondent
    )
  }

  get canViewDocumentTypes(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.DocumentType
    )
  }

  get canViewStoragePaths(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.StoragePath
    )
  }

  get canViewCustomFields(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.CustomField
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
    if (this.canViewTags) return DocumentAttributesNavIDs.Tags
    if (this.canViewCorrespondents)
      return DocumentAttributesNavIDs.Correspondents
    if (this.canViewDocumentTypes) return DocumentAttributesNavIDs.DocumentTypes
    if (this.canViewStoragePaths) return DocumentAttributesNavIDs.StoragePaths
    if (this.canViewCustomFields) return DocumentAttributesNavIDs.CustomFields
    return null
  }

  private getNavIDForSection(section: string): DocumentAttributesNavIDs | null {
    if (!section) return null
    const navIDKey: string = Object.keys(DocumentAttributesNavIDs).find(
      (navID) => navID.toLowerCase() === section.toLowerCase()
    )
    if (!navIDKey) return null

    const navID = DocumentAttributesNavIDs[navIDKey]
    if (!this.isNavIDAllowed(navID)) return null
    return navID
  }

  private getSectionForNavID(navID: number): string | null {
    if (!this.isNavIDAllowed(navID)) return null
    const [foundNavIDKey] = Object.entries(DocumentAttributesNavIDs).find(
      ([, navIDValue]) => navIDValue === navID
    )
    return foundNavIDKey?.toLowerCase() ?? null
  }

  private isNavIDAllowed(navID: number): boolean {
    switch (navID) {
      case DocumentAttributesNavIDs.Tags:
        return this.canViewTags
      case DocumentAttributesNavIDs.Correspondents:
        return this.canViewCorrespondents
      case DocumentAttributesNavIDs.DocumentTypes:
        return this.canViewDocumentTypes
      case DocumentAttributesNavIDs.StoragePaths:
        return this.canViewStoragePaths
      case DocumentAttributesNavIDs.CustomFields:
        return this.canViewCustomFields
      default:
        return false
    }
  }
}
