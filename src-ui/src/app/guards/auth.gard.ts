import {
  CanActivate,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
} from '@angular/router'
import { Injectable } from '@angular/core'
import { SettingsService } from '../services/settings.service'

@Injectable()
export class AuthGard implements CanActivate {
  constructor(public settingsService: SettingsService) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean {
    return this.settingsService.currentUserCan(route.data.requiredPermission)
  }
}
