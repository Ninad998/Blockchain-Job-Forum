from datetime import datetime
import hashlib


class Block(object):

    def __init__(self, index, proof, previous_hash, body, creation=None):
        """
        Parameters of each block
        1) index: This is the index of the Block in Block-chain 
        2) Proof: This is a number which will be generated during mining and after successful mining,
                a Block will be created using this Proof.
        3) Previous_hash: This will hold the hash of the previous Block in the Blockchain.
        4) Body: A list which will store all data records.
        5) Hash: This the hash calculated based on the body data and previous hash.
        6) Nonce: This the number which will be generated during the process of calculating the hash of block,
                this number make the hash to have two zeros as its prefix.

        """
        self.index = index
        self.proof = proof
        self.previous_hash = previous_hash
        self.body = body
        self.creation = creation or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.nonce, self.hash = self.compute_hash_with_proof_of_work()

    def compute_hash_with_proof_of_work( self, difficulty="00" ):
        """
        Generate "HASH with Proof Of Work"
        - Find a number such that, hash value always starts with two zeros "00".
        """
        
        nonce = 0
        while True:  
          hash = self.get_block_hash( nonce )
          if hash.startswith( difficulty ):
            return [nonce,hash]
          else:
            nonce += 1

    def get_block_hash(self, nonce=0):
        """
        Hash based upon the block data and previous block hash. 
        """
        block_string = "{}{}{}{}{}{}".format(str(nonce), self.index, self.proof, self.previous_hash, self.body, self.creation)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def __repr__(self):
        """
        Storage of block containt into block as string to save memory space.
        """
        return "{} - {} - {} - {} - {} - {} - {}".format(self.index, self.proof, self.previous_hash, self.body, self.creation, self.nonce, self.hash)


class BlockChain(object):

    def __init__(self):
        """
        Blockchain parameters:
        chain : list, contains the whole chain of blocks.
        current_node_transactions = list, contains the blocks data before mining into blockchain.
        node: set, stores neighbour's details of the peer.
        create genesis block: function, create the initial block of the blockchain.
        """
        self.chain = []
        self.current_node_transactions = []
        self.nodes = set()
        self.create_genesis_block()

    @property
    def get_serialized_chain(self):
        return [vars(block) for block in self.chain]

    def remove_block_in_chain(self,block_id):
        self.chain.pop(block_id)
        
    def create_genesis_block(self):
        self.create_new_block(proof=0, previous_hash=0)

    def create_new_block(self, proof, previous_hash):
        """
        Once the block is mined the block is added to blockchain.
        index: int, works as the block id.
        """
        if len(self.chain) == 0:
            block_index = 1
        else:
            block_index =self.chain[-1].index + 1
        block = Block(
            index=block_index,
            proof=proof,
            previous_hash=previous_hash,
            body=self.current_node_transactions
        )
        # Reset the transaction list
        self.current_node_transactions = []  

        self.chain.append(block)
        return block

    @staticmethod
    def is_valid_block(block, previous_block):
        if previous_block.index + 1 != block.index:
            return False

        elif previous_block.get_block_hash != block.previous_hash:
            return False

        elif not BlockChain.is_valid_proof(block.proof, previous_block.proof):
            return False

        elif block.creation <= previous_block.creation:
            return False

        return True

    def create_new_transaction(self, data):
        """
        The each feature is stored as different parameter in block.
        feature: user, job, application, transaction, message, mine_transactions
        """
        self.current_node_transactions.append({
            'user': data.get('user',{}),
            'job': data.get('job',{}),
            'application': data.get('application',{}),
            'transaction': data.get('transaction',{}),
            'message': data.get('message',{}),
            'mine_transactions':data.get('mine_transactions',{})
        })
        return True

    @staticmethod
    def is_valid_transaction():
        # Not Implemented
        pass

    @staticmethod
    def create_proof_of_work(previous_proof):
        """
        Generate "Proof Of Work"

        A very simple `Proof of Work` Algorithm -
            - Find a number such that, sum of the number and previous POW number is divisible by 7
        """
        proof = previous_proof + 1
        while not BlockChain.is_valid_proof(proof, previous_proof):
            proof += 1

        return proof

    @staticmethod
    def is_valid_proof(proof, previous_proof):
        return (proof + previous_proof) % 7 == 0

    @property
    def get_last_block(self):
        return self.chain[-1]

    def is_valid_chain(self):
        """
        Check if given blockchain is valid
        """
        previous_block = self.chain[0]
        current_index = 1

        while current_index < len(self.chain):

            block = self.chain[current_index]

            if not self.is_valid_block(block, previous_block):
                return False

            previous_block = block
            current_index += 1

        return True

    def mine_block(self, sender_address, miner_address):
        """
        For mining the Block(or finding the proof),
        we must be awarded with some amount(in our case this is 1)
        """
        
        self.current_node_transactions[-1]['mine_transactions']={'sender':sender_address,
                                'recipient':miner_address,
                                'amount':1}

        last_block = self.get_last_block

        last_proof = last_block.proof
        proof = self.create_proof_of_work(last_proof)

        last_hash = last_block.hash
        block = self.create_new_block(proof, last_hash)

        return vars(block)

    def create_node(self, addresses):
        """
        Stores the peer neighbour's details into our data structure node.
        """
        for address in addresses:
            self.nodes.add(address)
        return True

    @staticmethod
    def get_block_object_from_block_data(block_data):
        return Block(
            block_data['index'],
            block_data['proof'],
            block_data['previous_hash'],
            block_data['body'],
            creation=block_data['creation']
        )
