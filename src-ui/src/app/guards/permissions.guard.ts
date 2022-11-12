import {
  CanActivate,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
} from '@angular/router'
import { Injectable } from '@angular/core'
import { PermissionsService } from '../services/permissions.service'

@Injectable()
export class PermissionsGuard implements CanActivate {
  constructor(private permissionsService: PermissionsService) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean {
    return this.permissionsService.currentUserCan(route.data.requiredPermission)
  }
}
