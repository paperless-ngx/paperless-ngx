import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from 'src/app/services/auth.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent implements OnInit {

  constructor(private auth: AuthService, private router: Router, private toastService: ToastService) { }

  loginForm = new FormGroup({
    username: new FormControl(''),
    password: new FormControl(''),
    rememberMe: new FormControl(false)
  })

  ngOnInit(): void {
  }

  loginClicked() {
    this.auth.login(this.loginForm.value.username, this.loginForm.value.password, this.loginForm.value.rememberMe).subscribe(result => {
      this.router.navigate([''])
    }, (error) => {
      this.toastService.showError("Unable to log in with provided credentials.")
    }
    )
  }

}
