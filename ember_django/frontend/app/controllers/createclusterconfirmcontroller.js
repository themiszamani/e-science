// Createcluster confirm controller
Orka.CreateclusterConfirmController = Ember.Controller.extend({
        // in order to have access to personalize
        needs : 'createclusterIndex',
        message : '',
        actions : {
                logout : function() {
                        // redirect to logout
                        this.transitionTo('user.logout');
                },
                // when previous button is pressed
                // gotoflavor action is triggered
                gotoflavor : function() {
                        // redirect to flavor template
                        this.set('message', '');
                        this.transitionTo('createcluster.index');
                },
                // when next button is pressed
                // gotocreate action is triggered
                // User's cluster creation choices are send to backend for checking
                gotocreate : function() {
                        var self = this;
                        var cluster_selection = this.store.update('clusterchoice', {
                                'id' : 1,
                                'cluster_name' : this.controllerFor('createclusterIndex').get('cluster_name'),
                                'cluster_size' : this.controllerFor('createclusterIndex').get('cluster_size'),
                                'cpu_master' : this.controllerFor('createclusterIndex').get('master_cpu_selection'),
                                'mem_master' : this.controllerFor('createclusterIndex').get('master_mem_selection'),
                                'disk_master' : this.controllerFor('createclusterIndex').get('master_disk_selection'),
                                'cpu_slaves' : this.controllerFor('createclusterIndex').get('slaves_cpu_selection'),
                                'mem_slaves' : this.controllerFor('createclusterIndex').get('slaves_mem_selection'),
                                'disk_slaves' : this.controllerFor('createclusterIndex').get('slaves_disk_selection'),
                                'disk_template' : this.controllerFor('createclusterIndex').get('disk_temp'),
                                'os_choice' : this.controllerFor('createclusterIndex').get('operating_system')
                        }).save();
                        cluster_selection.then(function(data) {
                                // Set the response to user's create cluster click when put succeeds.
                                self.set('message', data._data.message);
                        }, function() {
                                // Set the response to user's create cluster click when put fails.
                                self.set('message', 'A problem occured during your request. Please check your cluster parameters and try again');
                        });
                }
        }
});
