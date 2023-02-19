import {
  CanActivate,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
  UrlTree,
  Router,
} from '@angular/router'
import { Injectable } from '@angular/core'
import { PermissionsService } from '../services/permissions.service'
import { ToastService } from '../services/toast.service'

@Injectable()
export class PermissionsGuard implements CanActivate {
  constructor(
    private permissionsService: PermissionsService,
    private router: Router,
    private toastService: ToastService
  ) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean | UrlTree {
    if (
      !this.permissionsService.currentUserCan(
        route.data.requiredPermission.action,
        route.data.requiredPermission.type
      )
    ) {
      this.toastService.showError(
        $localize`You don't have permissions to do that`
      )
      return this.router.parseUrl('/dashboard')
    } else {
      return true
    }
  }
}
