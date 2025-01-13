import { Injectable } from '@angular/core'
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { PermissionsService } from '../services/permissions.service'
import { ToastService } from '../services/toast.service'

@Injectable()
export class PermissionsGuard {
  constructor(
    private permissionsService: PermissionsService,
    private router: Router,
    private toastService: ToastService,
    private tourService: TourService
  ) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean | UrlTree {
    if (
      (route.data.requireAdmin && !this.permissionsService.isAdmin()) ||
      (route.data.requiredPermission &&
        !this.permissionsService.currentUserCan(
          route.data.requiredPermission.action,
          route.data.requiredPermission.type
        ))
    ) {
      // Check if tour is running 1 = TourState.ON
      if (this.tourService.getStatus() !== 1) {
        this.toastService.showError(
          $localize`You don't have permissions to do that`
        )
      }
      return this.router.parseUrl('/dashboard')
    } else {
      return true
    }
  }
}
