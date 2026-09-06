import { Component, inject, signal } from '@angular/core'
import { ActivatedRoute, Router } from '@angular/router'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ShareLinkBundleListComponent } from './share-link-bundle-list/share-link-bundle-list.component'
import { ShareLinkListComponent } from './share-link-list/share-link-list.component'

export enum ShareLinksNavIDs {
  DocumentLinks = 'documents',
  Bundles = 'bundles',
}

@Component({
  selector: 'pngx-share-links',
  templateUrl: './share-links.component.html',
  imports: [
    NgbNavModule,
    PageHeaderComponent,
    ShareLinkBundleListComponent,
    ShareLinkListComponent,
  ],
})
export class ShareLinksComponent {
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly permissionsService = inject(PermissionsService)

  readonly ShareLinksNavIDs = ShareLinksNavIDs
  readonly activeNavID = signal(this.getInitialNavID())

  get canViewDocumentLinks(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.ShareLink
    )
  }

  get canViewBundles(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.ShareLinkBundle
    )
  }

  selectTab(tab: ShareLinksNavIDs): void {
    this.activeNavID.set(tab)
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { type: tab },
      queryParamsHandling: 'merge',
    })
  }

  private getInitialNavID(): ShareLinksNavIDs {
    const requestedTab = this.route.snapshot.queryParamMap.get('type')
    if (requestedTab === ShareLinksNavIDs.Bundles && this.canViewBundles) {
      return ShareLinksNavIDs.Bundles
    }
    if (this.canViewDocumentLinks) {
      return ShareLinksNavIDs.DocumentLinks
    }
    return ShareLinksNavIDs.Bundles
  }
}
