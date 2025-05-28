import { Routes } from '@angular/router'
import { Access } from './access'
import { Login } from './login'
import { Error } from './error'

export default [
    { path: 'access', component: Access },
    { path: 'error', component: Error },
    { path: 'login', component: Login },
] as Routes
