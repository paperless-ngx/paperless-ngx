describe('settings', () => {
  beforeEach(() => {
    // also uses global fixtures from cypress/support/e2e.ts

    this.modifiedViews = []

    // mock API methods
    cy.intercept('http://localhost:8000/api/ui_settings/', {
      fixture: 'ui_settings/settings.json',
    }).then(() => {
      cy.fixture('saved_views/savedviews.json').then((savedViewsJson) => {
        // saved views PATCH
        cy.intercept(
          'PATCH',
          'http://localhost:8000/api/saved_views/*',
          (req) => {
            this.modifiedViews.push(req.body) // store this for later
            req.reply({ result: 'OK' })
          }
        )

        cy.intercept(
          'GET',
          'http://localhost:8000/api/saved_views/*',
          (req) => {
            let response = { ...savedViewsJson }
            if (this.modifiedViews.length) {
              response.results = response.results.map((v) => {
                if (this.modifiedViews.find((mv) => mv.id == v.id))
                  v = this.modifiedViews.find((mv) => mv.id == v.id)
                return v
              })
            }

            req.reply(response)
          }
        ).as('savedViews')
      })

      this.newMailAccounts = []

      cy.intercept(
        'POST',
        'http://localhost:8000/api/mail_accounts/',
        (req) => {
          const newRule = req.body
          newRule.id = 3
          this.newMailAccounts.push(newRule) // store this for later
          req.reply({ result: 'OK' })
        }
      ).as('saveAccount')

      cy.fixture('mail_accounts/mail_accounts.json').then(
        (mailAccountsJson) => {
          cy.intercept(
            'GET',
            'http://localhost:8000/api/mail_accounts/*',
            (req) => {
              console.log(req, this.newMailAccounts)

              let response = { ...mailAccountsJson }
              if (this.newMailAccounts.length) {
                response.results = response.results.concat(this.newMailAccounts)
              }

              req.reply(response)
            }
          ).as('getAccounts')
        }
      )

      this.newMailRules = []

      cy.intercept('POST', 'http://localhost:8000/api/mail_rules/', (req) => {
        const newRule = req.body
        newRule.id = 2
        this.newMailRules.push(newRule) // store this for later
        req.reply({ result: 'OK' })
      }).as('saveRule')

      cy.fixture('mail_rules/mail_rules.json').then((mailRulesJson) => {
        cy.intercept('GET', 'http://localhost:8000/api/mail_rules/*', (req) => {
          let response = { ...mailRulesJson }
          if (this.newMailRules.length) {
            response.results = response.results.concat(this.newMailRules)
          }

          req.reply(response)
        }).as('getRules')
      })

      cy.fixture('documents/documents.json').then((documentsJson) => {
        cy.intercept('GET', 'http://localhost:8000/api/documents/1/', (req) => {
          let response = { ...documentsJson }
          response = response.results.find((d) => d.id == 1)
          req.reply(response)
        })
      })
    })

    cy.viewport(1024, 1600)
    cy.visit('/settings')
  })

  it('should activate / deactivate save button when settings change and are saved', () => {
    cy.contains('button', 'Save').should('be.disabled')
    cy.contains('Use system settings').click()
    cy.contains('button', 'Save').should('not.be.disabled')
    cy.contains('button', 'Save').click()
    cy.contains('button', 'Save').should('be.disabled')
  })

  it('should warn on unsaved changes', () => {
    cy.contains('Use system settings').click()
    cy.contains('a', 'Dashboard').click()
    cy.contains('You have unsaved changes')
    cy.contains('button', 'Cancel').click()
    cy.contains('button', 'Save').click().wait('@savedViews').wait(2000)
    cy.contains('a', 'Dashboard').click()
    cy.contains('You have unsaved changes').should('not.exist')
  })

  it('should apply appearance changes when set', () => {
    cy.contains('Use system settings').click()
    cy.get('body').should('not.have.class', 'color-scheme-system')
    cy.contains('Enable dark mode').click()
    cy.get('body').should('have.class', 'color-scheme-dark')
  })

  it('should remove saved view from sidebar when unset', () => {
    cy.contains('a', 'Saved views').click().wait(2000)
    cy.get('#show_in_sidebar_1').click()
    cy.contains('button', 'Save').click().wait('@savedViews').wait(2000)
    cy.contains('li', 'Inbox').should('not.exist')
  })

  it('should remove saved view from dashboard when unset', () => {
    cy.contains('a', 'Saved views').click()
    cy.get('#show_on_dashboard_1').click()
    cy.contains('button', 'Save').click().wait('@savedViews').wait(2000)
    cy.visit('/dashboard')
    cy.get('app-saved-view-widget').contains('Inbox').should('not.exist')
  })

  it('should show a list of mail accounts & rules & support creation', () => {
    cy.contains('a', 'Mail').click()
    cy.get('app-settings .tab-content ul li').its('length').should('eq', 5) // 2 headers, 2 accounts, 1 rule
    cy.contains('button', 'Add Account').click()
    cy.contains('Create new mail account')
    cy.get('app-input-text[formcontrolname="name"]').type(
      'Example Mail Account'
    )
    cy.get('app-input-text[formcontrolname="imap_server"]').type(
      'mail.example.com'
    )
    cy.get('app-input-text[formcontrolname="imap_port"]').type('993')
    cy.get('app-input-text[formcontrolname="username"]').type('username')
    cy.get('app-input-password[formcontrolname="password"]').type('pass')
    cy.contains('app-mail-account-edit-dialog button', 'Save')
      .click()
      .wait('@saveAccount')
      .wait('@getAccounts')
    cy.contains('Saved account')

    cy.wait(1000)
    cy.contains('button', 'Add Rule').click()
    cy.contains('Create new mail rule')
    cy.get('app-input-text[formcontrolname="name"]').type('Example Rule')
    cy.get('app-input-select[formcontrolname="account"]').type('Example{enter}')
    cy.get('app-input-number[formcontrolname="maximum_age"]').type('30')
    cy.get('app-input-text[formcontrolname="filter_subject"]').type(
      '[paperless]'
    )
    cy.contains('app-mail-rule-edit-dialog button', 'Save')
      .click()
      .wait('@saveRule')
      .wait('@getRules')
    cy.contains('Saved rule').wait(1000)

    cy.get('app-settings .tab-content ul li').its('length').should('eq', 7)
  })
})
